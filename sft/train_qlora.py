"""
QLoRA Fine-tuning Script with LangChain Integration

This script fine-tunes openai/gpt-oss-20b using QLoRA (Quantized Low-Rank Adaptation)
with LangChain for data loading and prompt formatting.

Usage:
    uv run train_qlora.py

Requirements:
    uv sync  # Install dependencies from requirements.txt
"""

import os
import torch
from dataclasses import dataclass, field
from typing import List, Dict

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# LangChain imports
from langchain_community.document_loaders import CSVLoader
from langchain_core.prompts import PromptTemplate

# Hugging Face imports
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training


@dataclass
class QLoRAConfig:
    """
    Configuration for QLoRA fine-tuning
    
    This class contains all hyperparameters and settings for:
    - Model selection and loading
    - Data processing
    - Quantization (4-bit compression)
    - LoRA adapters (which layers to train)
    - Training hyperparameters
    """
    
    # ============ Model Settings ============
    model_name: str = "meta-llama/Llama-2-7b-hf"
    """Base model to fine-tune. Using Llama-2-7b-hf for QLoRA training.
    Requires HUGGINGFACE_API_KEY in .env file for authentication.
    Alternative models: mistralai/Mistral-7B-v0.1, tiiuae/falcon-7b"""
    
    # ============ Data Settings ============
    csv_path: str = "training_data.csv"
    """Path to CSV file with 'instruction' and 'response' columns"""
    
    max_length: int = 512
    """Maximum sequence length in tokens. Longer sequences are truncated."""
    
    # ============ Quantization Settings (QLoRA) ============
    load_in_4bit: bool = True
    """Enable 4-bit quantization to reduce memory from 80GB to ~12GB"""
    
    bnb_4bit_compute_dtype: str = "float16"
    """Compute dtype for 4-bit base models (float16 or bfloat16)"""
    
    bnb_4bit_quant_type: str = "nf4"
    """Quantization type: 'nf4' (NormalFloat4) or 'fp4' (Float4)"""
    
    use_nested_quant: bool = True
    """Enable nested quantization for additional memory savings"""
    
    # ============ LoRA Settings ============
    lora_r: int = 64
    """LoRA rank. Higher = more parameters to train. Range: 8-128"""
    
    lora_alpha: int = 16
    """LoRA scaling factor. Usually lora_alpha = lora_r or lora_r/2"""
    
    lora_dropout: float = 0.1
    """Dropout probability for LoRA layers. Helps prevent overfitting."""
    
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj"]
    )
    """Which attention layers to add LoRA adapters to. These are the query, key, value, and output projections."""
    
    # ============ Training Settings ============
    output_dir: str = "./qlora-gpt-oss-20b"
    """Directory to save trained model and checkpoints"""
    
    num_train_epochs: int = 3
    """Number of complete passes through the training data"""
    
    per_device_train_batch_size: int = 1
    """Batch size per GPU. Set to 1 for 12GB GPU, can increase for larger GPUs."""
    
    gradient_accumulation_steps: int = 4
    """Accumulate gradients over N steps before updating. Effective batch size = batch_size * accumulation_steps"""
    
    learning_rate: float = 2e-4
    """Learning rate (0.0002). How fast the model learns."""
    
    max_grad_norm: float = 0.3
    """Gradient clipping. Prevents exploding gradients."""
    
    warmup_ratio: float = 0.03
    """Warmup 3% of training steps with linearly increasing learning rate"""
    
    lr_scheduler_type: str = "cosine"
    """Learning rate scheduler: 'cosine', 'linear', or 'constant'"""
    
    logging_steps: int = 10
    """Log training metrics every N steps"""
    
    save_steps: int = 100
    """Save checkpoint every N steps"""
    
    save_total_limit: int = 3
    """Keep only the last N checkpoints to save disk space"""
    
    fp16: bool = True
    """Enable mixed precision training (FP16) for speed and memory"""
    
    optim: str = "paged_adamw_32bit"
    """Optimizer: paged_adamw_32bit is memory-efficient"""
    
    # ============ Memory Optimization ============
    gradient_checkpointing: bool = True
    """Trade compute for memory. Saves memory at cost of ~20% slower training."""
    
    group_by_length: bool = True
    """Group sequences of similar length to minimize padding"""


# LangChain Prompt Template for Alpaca format
ALPACA_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["instruction", "response"],
    template=(
        "Below is an instruction that describes a task. "
        "Write a response that appropriately completes the request.\n\n"
        "### Instruction:\n{instruction}\n\n"
        "### Response:\n{response}"
    )
)


def load_and_format_data(csv_path: str) -> Dataset:
    """
    Load CSV data using LangChain's CSVLoader and format using PromptTemplate
    
    This function demonstrates LangChain integration:
    1. Uses CSVLoader to read CSV and create Document objects
    2. Uses PromptTemplate to format instruction/response pairs into Alpaca format
    
    Args:
        csv_path: Path to CSV file with 'instruction' and 'response' columns
        
    Returns:
        HuggingFace Dataset with formatted text ready for training
        
    Example CSV:
        instruction,response
        "What is Python?","Python is a programming language"
        "Calculate 2+2","2+2 equals 4"
    """
    print(f"Loading training data from {csv_path} using LangChain CSVLoader...")
    
    # Use LangChain's CSVLoader to load data
    loader = CSVLoader(
        file_path=csv_path,
        encoding="utf-8",
        csv_args={
            'delimiter': ',',
            'quotechar': '"',
        }
    )
    
    documents = loader.load()
    print(f"Loaded {len(documents)} documents from CSV")
    
    # Extract instruction and response from documents and format using LangChain PromptTemplate
    formatted_texts = []
    for doc in documents:
        # CSVLoader stores data in page_content as "instruction: ...\nresponse: ..."
        # Parse the page_content to extract instruction and response
        content = doc.page_content
        lines = content.split('\n')
        
        instruction = ""
        response = ""
        
        for line in lines:
            if line.startswith('instruction: '):
                instruction = line.replace('instruction: ', '').strip()
            elif line.startswith('response: '):
                response = line.replace('response: ', '').strip()
        
        # Format using LangChain's PromptTemplate
        formatted_text = ALPACA_PROMPT_TEMPLATE.format(
            instruction=instruction,
            response=response
        )
        formatted_texts.append(formatted_text)
    
    # Convert to HuggingFace Dataset
    dataset = Dataset.from_dict({"text": formatted_texts})
    
    print(f"Formatted {len(dataset)} training examples using Alpaca template")
    print("\nExample formatted text:")
    print("-" * 80)
    print(dataset[0]['text'][:300] + "...")
    print("-" * 80)
    
    return dataset


def setup_model_and_tokenizer(config: QLoRAConfig):
    """
    Setup model with 4-bit quantization and tokenizer
    
    This function:
    1. Configures 4-bit quantization using BitsAndBytes
    2. Loads the base model (20B parameters) in quantized form
    3. Prepares model for k-bit training (freezes base weights, prepares for adapters)
    4. Loads tokenizer
    
    Memory savings: Without quantization, 20B model needs ~80GB.
    With 4-bit quantization: ~12-14GB
    
    Args:
        config: QLoRAConfig with model settings
        
    Returns:
        Tuple of (model, tokenizer)
    """
    print(f"\n{'='*80}")
    print(f"Loading model: {config.model_name}")
    print(f"{'='*80}")
    
    # ============ Step 1: Configure 4-bit Quantization ============
    # BitsAndBytes Config reduces model precision from 32-bit to 4-bit
    # This is the "Q" in QLoRA (Quantized)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=config.load_in_4bit,
        bnb_4bit_compute_dtype=getattr(torch, config.bnb_4bit_compute_dtype),
        bnb_4bit_quant_type=config.bnb_4bit_quant_type,
        bnb_4bit_use_double_quant=config.use_nested_quant,
    )
    
    print("\n4-bit Quantization Config:")
    print(f"  - Quantization type: {config.bnb_4bit_quant_type}")
    print(f"  - Compute dtype: {config.bnb_4bit_compute_dtype}")
    print(f"  - Nested quantization: {config.use_nested_quant}")
    
    # ============ Get HuggingFace API Token ============
    hf_token = os.getenv("HUGGINGFACE_API_KEY")
    if not hf_token:
        print("\n⚠️  WARNING: HUGGINGFACE_API_KEY not found in .env")
        print("Some models (like Llama-2) require authentication.")
        print("Add HUGGINGFACE_API_KEY to your .env file to access gated models.")
    else:
        print("\n✓ HuggingFace authentication configured")
    
    # ============ Step 2: Load Model with Quantization ============
    # This downloads the model (if not cached) and loads it in 4-bit format
    print("\nLoading model (this may take a few minutes)...")
    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        quantization_config=bnb_config,
        device_map="auto",  # Automatically distribute across available GPUs
        trust_remote_code=True,
        token=hf_token  # HuggingFace authentication token
    )
    
    # ============ Step 3: Prepare for k-bit Training ============
    # This prepares the quantized model for training by:
    # - Freezing the base model weights
    # - Setting up gradient computation for LoRA adapters
    model = prepare_model_for_kbit_training(model)
    
    # ============ Step 4: Enable Gradient Checkpointing ============
    # Trades compute for memory (re-computes activations during backward pass)
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        print("Gradient checkpointing enabled (saves memory)")
    
    # ============ Step 5: Load Tokenizer ============
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_name,
        trust_remote_code=True,
        token=hf_token  # HuggingFace authentication token
    )
    
    # Set pad token if not exists (needed for batching)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = model.config.eos_token_id
    
    # Print model info
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel loaded successfully!")
    print(f"Total parameters: {total_params:,}")
    print(f"Memory footprint: ~{total_params * 4 / 1e9:.2f} GB (4-bit quantized)")
    
    return model, tokenizer


def setup_lora(model, config: QLoRAConfig):
    """
    Setup LoRA (Low-Rank Adaptation) adapters
    
    This is the "LoRA" part of QLoRA. Instead of training all 20 billion parameters,
    we add small "adapter" layers (low-rank matrices) to specific parts of the model
    and only train those.
    
    Think of it like adding tuning knobs to a complex machine - we're not replacing
    the gears, just adding controls to adjust behavior.
    
    Args:
        model: The base model (already quantized)
        config: QLoRAConfig with LoRA settings
        
    Returns:
        Model with LoRA adapters attached
    """
    print(f"\n{'='*80}")
    print("Setting up LoRA adapters")
    print(f"{'='*80}")
    
    # ============ Configure LoRA ============
    lora_config = LoraConfig(
        r=config.lora_r,  # Rank of the low-rank matrices
        lora_alpha=config.lora_alpha,  # Scaling factor
        target_modules=config.target_modules,  # Which layers to adapt
        lora_dropout=config.lora_dropout,  # Dropout for regularization
        bias="none",  # Don't adapt bias terms
        task_type="CAUSAL_LM"  # Task type: Causal Language Modeling
    )
    
    print(f"\nLoRA Configuration:")
    print(f"  - Rank (r): {config.lora_r}")
    print(f"  - Alpha: {config.lora_alpha}")
    print(f"  - Dropout: {config.lora_dropout}")
    print(f"  - Target modules: {config.target_modules}")
    
    # ============ Apply LoRA to Model ============
    model = get_peft_model(model, lora_config)
    
    # ============ Print Trainable Parameters ============
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    all_params = sum(p.numel() for p in model.parameters())
    trainable_percent = 100 * trainable_params / all_params
    
    print(f"\nParameter Breakdown:")
    print(f"  - Trainable params: {trainable_params:,}")
    print(f"  - All params: {all_params:,}")
    print(f"  - Trainable: {trainable_percent:.4f}%")
    print(f"\nWith LoRA, we train only {trainable_percent:.2f}% of parameters!")
    print(f"This is ~{trainable_params / 1e6:.0f}M parameters instead of {all_params / 1e9:.1f}B")
    
    return model


def preprocess_dataset(dataset, tokenizer, config: QLoRAConfig):
    """
    Tokenize dataset and prepare for training
    
    This function converts text into token IDs that the model can process.
    
    What is tokenization?
    - Text: "Hello world"
    - Tokens: ["Hello", " world"]
    - Token IDs: [15496, 995] (numbers the model understands)
    
    Args:
        dataset: HuggingFace Dataset with 'text' column
        tokenizer: Tokenizer for converting text to IDs
        config: QLoRAConfig with max_length setting
        
    Returns:
        Tokenized dataset ready for training
    """
    print(f"\n{'='*80}")
    print("Preprocessing dataset")
    print(f"{'='*80}")
    
    def tokenize_function(examples):
        """
        Tokenize a batch of examples
        
        For causal language modeling, we want the model to predict the next token.
        So we set labels = input_ids (shifted by 1 internally by the model)
        """
        # Tokenize texts
        outputs = tokenizer(
            examples['text'],
            truncation=True,  # Cut sequences longer than max_length
            max_length=config.max_length,
            padding="max_length",  # Pad shorter sequences
            return_tensors=None  # Return as lists, not tensors yet
        )
        
        # For causal LM, labels are the same as input_ids
        # The model will internally shift them by 1 for next-token prediction
        outputs["labels"] = outputs["input_ids"].copy()
        
        return outputs
    
    # Apply tokenization to entire dataset in batches
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,  # Remove original text column
        desc="Tokenizing dataset"
    )
    
    print(f"\nDataset tokenized successfully!")
    print(f"  - Total examples: {len(tokenized_dataset)}")
    print(f"  - Max sequence length: {config.max_length} tokens")
    print(f"  - Columns: {tokenized_dataset.column_names}")
    
    return tokenized_dataset


def train_model(model, tokenizer, train_dataset, config: QLoRAConfig):
    """
    Train the model using HuggingFace Trainer
    
    This function sets up the training loop and trains the LoRA adapters.
    
    Training process:
    1. Model sees a batch of examples
    2. Makes predictions (forward pass)
    3. Calculates error/loss
    4. Computes gradients (backward pass)
    5. Updates LoRA adapter weights
    6. Repeat for all batches → 1 epoch
    7. Repeat for N epochs
    
    Args:
        model: Model with LoRA adapters
        tokenizer: Tokenizer
        train_dataset: Preprocessed training data
        config: QLoRAConfig with training settings
    """
    print(f"\n{'='*80}")
    print("Starting training")
    print(f"{'='*80}")
    
    # ============ Training Arguments ============
    # These control how training happens
    training_args = TrainingArguments(
        # Output settings
        output_dir=config.output_dir,
        
        # Training schedule
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        
        # Optimization
        learning_rate=config.learning_rate,
        max_grad_norm=config.max_grad_norm,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        optim=config.optim,
        
        # Logging and saving
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        save_total_limit=config.save_total_limit,
        
        # Performance
        fp16=config.fp16,
        gradient_checkpointing=config.gradient_checkpointing,
        group_by_length=config.group_by_length,
        
        # Disable external logging
        report_to="none",
    )
    
    print(f"\nTraining Configuration:")
    print(f"  - Epochs: {config.num_train_epochs}")
    print(f"  - Batch size: {config.per_device_train_batch_size}")
    print(f"  - Gradient accumulation: {config.gradient_accumulation_steps}")
    print(f"  - Effective batch size: {config.per_device_train_batch_size * config.gradient_accumulation_steps}")
    print(f"  - Learning rate: {config.learning_rate}")
    print(f"  - Total training steps: {len(train_dataset) // (config.per_device_train_batch_size * config.gradient_accumulation_steps) * config.num_train_epochs}")
    
    # ============ Data Collator ============
    # Handles batching and prepares data for the model
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False  # We're doing causal LM, not masked LM
    )
    
    # ============ Initialize Trainer ============
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )
    
    # ============ Train! ============
    print(f"\n{'='*80}")
    print("Training started...")
    print(f"{'='*80}\n")
    
    trainer.train()
    
    # ============ Save Model ============
    print(f"\n{'='*80}")
    print("Training complete! Saving model...")
    print(f"{'='*80}")
    
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    
    print(f"\nModel and tokenizer saved to: {config.output_dir}")
    print(f"\nTo load your fine-tuned model:")
    print(f"  from peft import PeftModel")
    print(f"  from transformers import AutoModelForCausalLM, AutoTokenizer")
    print(f"  ")
    print(f"  base_model = AutoModelForCausalLM.from_pretrained('{config.model_name}')")
    print(f"  model = PeftModel.from_pretrained(base_model, '{config.output_dir}')")
    print(f"  tokenizer = AutoTokenizer.from_pretrained('{config.output_dir}')")


def main():
    """
    Main training pipeline
    
    This orchestrates the entire fine-tuning process:
    1. Load and format data using LangChain
    2. Setup quantized model
    3. Add LoRA adapters
    4. Tokenize data
    5. Train
    6. Save
    """
    print("\n" + "="*80)
    print("QLoRA Fine-tuning with LangChain Integration")
    print(f"Model: {QLoRAConfig().model_name}")
    print("="*80)
    
    # ============ Configuration ============
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "smart_lists_training.csv")
    output_dir = os.path.join(script_dir, "qlora-gpt-oss-20b")
    
    config = QLoRAConfig(
        csv_path=csv_path,  # Smart contact lists training data
        output_dir=output_dir  # Output directory
    )
    
    # ============ Hardware Check ============
    if not torch.cuda.is_available():
        print("\n⚠️  WARNING: CUDA not available!")
        print("Training on CPU will be extremely slow.")
        print(f"For QLoRA fine-tuning {config.model_name}, a GPU with at least 8-10GB VRAM is recommended.")
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            return
    else:
        print(f"\n✓ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"✓ GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        
        if torch.cuda.get_device_properties(0).total_memory < 8e9:
            print("\n⚠️  WARNING: GPU has less than 8GB memory.")
            print("Training may fail due to insufficient memory.")
    
    # ============ Step 1: Load and Format Data ============
    dataset = load_and_format_data(config.csv_path)
    
    # ============ Step 2: Setup Model and Tokenizer ============
    model, tokenizer = setup_model_and_tokenizer(config)
    
    # ============ Step 3: Setup LoRA ============
    model = setup_lora(model, config)
    
    # ============ Step 4: Preprocess Dataset ============
    train_dataset = preprocess_dataset(dataset, tokenizer, config)
    
    # ============ Step 5: Train ============
    train_model(model, tokenizer, train_dataset, config)
    
    # ============ Done! ============
    print("\n" + "="*80)
    print("✓ Fine-tuning completed successfully!")
    print(f"✓ Model saved to: {config.output_dir}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

