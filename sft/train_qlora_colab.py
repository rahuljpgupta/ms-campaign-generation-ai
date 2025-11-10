"""
QLoRA Fine-tuning Script for Google Colab

This script fine-tunes Llama-2-7b-hf using QLoRA for smart contact lists generation.

SETUP INSTRUCTIONS FOR GOOGLE COLAB:
=====================================
1. Go to: https://colab.research.google.com/
2. Upload this script
3. Enable GPU: Runtime → Change runtime type → Hardware accelerator → GPU (T4)
4. Upload your 'smart_lists_training.csv' file
5. Run all cells

BEFORE RUNNING:
===============
- Accept Llama-2 license: https://huggingface.co/meta-llama/Llama-2-7b-hf
- Get HuggingFace token: https://huggingface.co/settings/tokens

ESTIMATED TIME: ~20-25 minutes total
"""

import os
import torch
from dataclasses import dataclass, field
from typing import List

# Check if running in Colab
try:
    from google.colab import files
    import getpass
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
    print("Not running in Google Colab")

@dataclass
class QLoRAConfig:
    """Configuration for QLoRA fine-tuning"""
    
    # Model Settings
    model_name: str = "meta-llama/Llama-2-7b-hf"
    
    # Data Settings
    csv_path: str = "smart_lists_training.csv"
    
    # Output Settings
    output_dir: str = "./qlora-smart-lists"
    
    # Quantization Settings (4-bit)
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "float16"
    bnb_4bit_quant_type: str = "nf4"
    use_nested_quant: bool = True
    
    # LoRA Settings
    lora_r: int = 64
    lora_alpha: int = 16
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    
    # Training Settings
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 1
    learning_rate: float = 2e-4
    max_grad_norm: float = 0.3
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    
    # Memory Optimization
    gradient_checkpointing: bool = True
    optim: str = "paged_adamw_32bit"
    
    # Logging
    logging_steps: int = 10
    save_steps: int = 50


def check_gpu():
    """Check GPU availability"""
    print("="*80)
    print("GPU CHECK")
    print("="*80)
    
    if torch.cuda.is_available():
        print(f"✓ GPU Available: {torch.cuda.get_device_name(0)}")
        print(f"✓ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print(f"✓ CUDA Version: {torch.version.cuda}")
        return True
    else:
        print("⚠️  WARNING: No GPU detected!")
        if IN_COLAB:
            print("Go to: Runtime → Change runtime type → Hardware accelerator → GPU")
        return False


def install_dependencies():
    """Install required packages"""
    print("\n" + "="*80)
    print("INSTALLING DEPENDENCIES")
    print("="*80)
    print("\n⏳ Installing packages (this takes ~3-5 minutes)...\n")
    
    packages = [
        "torch",
        "transformers>=4.35.0",
        "datasets>=2.14.0",
        "peft>=0.7.0",
        "bitsandbytes>=0.41.0",
        "accelerate>=0.24.0",
        "langchain>=0.1.0",
        "langchain-core>=0.3.0",
        "langchain-community>=0.0.10",
        "pandas>=2.0.0",
        "scipy>=1.11.0",
        "trl>=0.7.0"
    ]
    
    import subprocess
    for package in packages:
        subprocess.check_call(["pip", "install", "-q", package])
    
    print("\n✓ All dependencies installed successfully!")


def setup_huggingface_auth():
    """Setup HuggingFace authentication"""
    print("\n" + "="*80)
    print("HUGGINGFACE AUTHENTICATION")
    print("="*80)
    print("\nGet your token from: https://huggingface.co/settings/tokens")
    print("Make sure you've accepted Llama-2 license at:")
    print("https://huggingface.co/meta-llama/Llama-2-7b-hf\n")
    
    if IN_COLAB:
        import getpass
        hf_token = getpass.getpass("Enter your HuggingFace token: ")
    else:
        hf_token = input("Enter your HuggingFace token: ")
    
    from huggingface_hub import login
    login(token=hf_token)
    
    print("\n✓ Successfully authenticated with HuggingFace!")
    return hf_token


def upload_training_data():
    """Upload training data file"""
    print("\n" + "="*80)
    print("UPLOAD TRAINING DATA")
    print("="*80)
    
    if IN_COLAB:
        # Check if file already exists in current directory
        if os.path.exists('smart_lists_training.csv'):
            print("\n✓ Found 'smart_lists_training.csv' in current directory")
            return 'smart_lists_training.csv'
        
        # Try to mount Google Drive
        print("\nOption 1: Mount Google Drive (recommended)")
        print("Option 2: Use file from current directory")
        print("\nTo use Google Drive:")
        print("  1. Uncomment and run: # from google.colab import drive; drive.mount('/content/drive')")
        print("  2. Copy your CSV to: /content/drive/MyDrive/")
        print("\nTo use current directory:")
        print("  1. Manually upload 'smart_lists_training.csv' to /content/ using Files panel (📁)")
        print("  2. Run this script again")
        
        # Try common paths
        possible_paths = [
            'smart_lists_training.csv',
            '/content/smart_lists_training.csv',
            '/content/drive/MyDrive/smart_lists_training.csv'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"\n✓ Found training data at: {path}")
                return path
        
        # If not found, provide manual input option
        print("\n⚠️  Training data not found in expected locations.")
        manual_path = input("Enter full path to CSV file (or press Enter to exit): ").strip()
        
        if not manual_path:
            print("\n❌ No training data provided. Exiting.")
            exit(1)
        
        if os.path.exists(manual_path):
            print(f"\n✓ Found training data: {manual_path}")
            return manual_path
        else:
            raise FileNotFoundError(f"File not found: {manual_path}")
    else:
        csv_path = input("Enter path to training CSV file: ")
        if os.path.exists(csv_path):
            print(f"\n✓ Found training data: {csv_path}")
            return csv_path
        else:
            raise FileNotFoundError(f"File not found: {csv_path}")


def load_and_format_data(csv_path):
    """Load and format training data using LangChain"""
    from langchain_community.document_loaders import CSVLoader
    from langchain_core.prompts import PromptTemplate
    from datasets import Dataset
    
    print("\n" + "="*80)
    print("LOADING TRAINING DATA")
    print("="*80)
    
    # Define Alpaca prompt template
    ALPACA_PROMPT_TEMPLATE = PromptTemplate(
        input_variables=["instruction", "response"],
        template="""Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Response:
{response}"""
    )
    
    # Load CSV
    loader = CSVLoader(file_path=csv_path, encoding="utf-8")
    documents = loader.load()
    print(f"\n✓ Loaded {len(documents)} documents from CSV")
    
    # Format data
    formatted_texts = []
    for doc in documents:
        content = doc.page_content
        lines = content.split('\n')
        
        instruction = ""
        response = ""
        
        for line in lines:
            if line.startswith('instruction: '):
                instruction = line.replace('instruction: ', '').strip()
            elif line.startswith('response: '):
                response = line.replace('response: ', '').strip()
        
        formatted_text = ALPACA_PROMPT_TEMPLATE.format(
            instruction=instruction,
            response=response
        )
        formatted_texts.append(formatted_text)
    
    # Convert to HuggingFace Dataset
    dataset = Dataset.from_dict({"text": formatted_texts})
    
    print(f"✓ Formatted {len(dataset)} training examples")
    print("\nExample formatted text:")
    print("-"*80)
    print(dataset[0]['text'][:300] + "...")
    print("-"*80)
    
    return dataset, ALPACA_PROMPT_TEMPLATE


def setup_model_and_tokenizer(config, hf_token):
    """Load model and tokenizer with quantization"""
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig
    )
    from peft import prepare_model_for_kbit_training
    
    print("\n" + "="*80)
    print(f"LOADING MODEL: {config.model_name}")
    print("="*80)
    
    # Configure 4-bit quantization
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
    
    # Load model
    print("\n⏳ Loading model (this may take a few minutes)...")
    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        token=hf_token
    )
    
    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model)
    
    # Enable gradient checkpointing
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        print("✓ Gradient checkpointing enabled")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_name,
        trust_remote_code=True,
        token=hf_token
    )
    
    # Set pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        model.config.pad_token_id = model.config.eos_token_id
    
    print("\n✓ Model and tokenizer loaded successfully!")
    print(f"✓ Model size: ~{sum(p.numel() for p in model.parameters()) / 1e9:.2f}B parameters")
    
    return model, tokenizer


def configure_lora(model, config):
    """Configure LoRA adapters"""
    from peft import LoraConfig, get_peft_model
    
    print("\n" + "="*80)
    print("CONFIGURING LORA ADAPTERS")
    print("="*80)
    
    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=config.target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    model = get_peft_model(model, lora_config)
    
    print("\nLoRA Configuration:")
    print(f"  - Rank (r): {config.lora_r}")
    print(f"  - Alpha: {config.lora_alpha}")
    print(f"  - Dropout: {config.lora_dropout}")
    print(f"  - Target modules: {', '.join(config.target_modules)}")
    
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    all_params = sum(p.numel() for p in model.parameters())
    trainable_percent = 100 * trainable_params / all_params
    
    print(f"\n✓ Trainable parameters: {trainable_params:,} ({trainable_percent:.2f}%)")
    print(f"✓ Total parameters: {all_params:,}")
    print(f"✓ Memory efficient: Only {trainable_percent:.2f}% of parameters will be updated!")
    
    return model


def tokenize_dataset(dataset, tokenizer):
    """Tokenize the dataset"""
    print("\n" + "="*80)
    print("TOKENIZING DATASET")
    print("="*80)
    
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=2048,
            padding="max_length"
        )
    
    print("\n⏳ Tokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names
    )
    
    print(f"✓ Tokenization complete!")
    print(f"✓ Dataset size: {len(tokenized_dataset)} examples")
    
    return tokenized_dataset


def train_model(model, tokenizer, tokenized_dataset, config):
    """Train the model"""
    from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
    
    print("\n" + "="*80)
    print("TRAINING CONFIGURATION")
    print("="*80)
    
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        max_grad_norm=config.max_grad_norm,
        warmup_ratio=config.warmup_ratio,
        lr_scheduler_type=config.lr_scheduler_type,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        save_total_limit=3,
        fp16=True,
        optim=config.optim,
        gradient_checkpointing=config.gradient_checkpointing,
        report_to="none"
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator
    )
    
    print("\nTraining Configuration:")
    print(f"  - Epochs: {config.num_train_epochs}")
    print(f"  - Batch size: {config.per_device_train_batch_size}")
    print(f"  - Learning rate: {config.learning_rate}")
    print(f"  - Optimizer: {config.optim}")
    print(f"  - FP16: Enabled")
    
    print("\n" + "="*80)
    print("STARTING TRAINING")
    print("="*80)
    print("\n⏳ Training in progress... This will take ~15-20 minutes.\n")
    
    # Train
    trainer.train()
    
    print("\n" + "="*80)
    print("✓ TRAINING COMPLETE!")
    print("="*80)
    
    return trainer


def save_model(model, tokenizer, config):
    """Save the fine-tuned model"""
    print("\n" + "="*80)
    print("SAVING MODEL")
    print("="*80)
    
    model.save_pretrained(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    
    print(f"\n✓ Model saved to: {config.output_dir}")
    print(f"✓ Tokenizer saved to: {config.output_dir}")


def test_model(model, tokenizer, prompt_template):
    """Test the fine-tuned model"""
    print("\n" + "="*80)
    print("TESTING FINE-TUNED MODEL")
    print("="*80)
    
    test_prompts = [
        "Find customers whose email contains gmail",
        "List people who booked in the last 7 days",
        "Show customers with first name John"
    ]
    
    for i, test_prompt in enumerate(test_prompts, 1):
        print(f"\nTest {i}:")
        print("-" * 80)
        print(f"Prompt: {test_prompt}")
        
        # Format with Alpaca template
        formatted_prompt = prompt_template.format(
            instruction=test_prompt,
            response=""
        )
        
        # Tokenize
        inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.7,
                do_sample=True,
                top_p=0.95
            )
        
        # Decode
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = generated_text.split("### Response:")[-1].strip()
        
        print(f"Generated: {response}")
        print("-" * 80)
    
    print("\n✓ Testing complete!")


def download_model(config):
    """Create zip for download (Colab only)"""
    import shutil
    
    print("\n" + "="*80)
    print("PREPARING MODEL FOR DOWNLOAD")
    print("="*80)
    
    zip_filename = "qlora-smart-lists-model"
    zip_path = shutil.make_archive(zip_filename, 'zip', config.output_dir)
    
    print(f"\n✓ Model archived as: {zip_filename}.zip")
    print(f"✓ Location: /content/{zip_filename}.zip")
    
    if IN_COLAB:
        print("\n📥 To download:")
        print("  1. Go to Files panel (📁) on the left")
        print(f"  2. Find '{zip_filename}.zip'")
        print("  3. Right-click → Download")
        print("\nOr use this command in a notebook cell:")
        print(f"  from google.colab import files; files.download('{zip_filename}.zip')")
    else:
        print(f"\n✓ Model files saved to: {config.output_dir}")
    
    return zip_path


def main():
    """Main training pipeline"""
    print("\n" + "="*80)
    print("QLoRA FINE-TUNING FOR SMART CONTACT LISTS")
    print("="*80)
    print("\nThis script will fine-tune Llama-2-7b-hf using QLoRA")
    print("Estimated time: ~20-25 minutes total\n")
    
    # Step 1: Check GPU
    if not check_gpu():
        print("\n⚠️  GPU required for training. Please enable GPU and restart.")
        return
    
    # Step 2: Install dependencies
    print("\nInstalling dependencies...")
    install_dependencies()
    
    # Step 3: Setup authentication
    hf_token = setup_huggingface_auth()
    
    # Step 4: Upload training data
    csv_path = upload_training_data()
    
    # Step 5: Configuration
    config = QLoRAConfig(csv_path=csv_path)
    print(f"\n✓ Configuration loaded")
    print(f"  - Model: {config.model_name}")
    print(f"  - Epochs: {config.num_train_epochs}")
    
    # Step 6: Load and format data
    dataset, prompt_template = load_and_format_data(csv_path)
    
    # Step 7: Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer(config, hf_token)
    
    # Step 8: Configure LoRA
    model = configure_lora(model, config)
    
    # Step 9: Tokenize dataset
    tokenized_dataset = tokenize_dataset(dataset, tokenizer)
    
    # Step 10: Train
    trainer = train_model(model, tokenizer, tokenized_dataset, config)
    
    # Step 11: Save model
    save_model(model, tokenizer, config)
    
    # Step 12: Test model
    test_model(model, tokenizer, prompt_template)
    
    # Step 13: Download (Colab only)
    download_model(config)
    
    print("\n" + "="*80)
    print("🎉 ALL DONE!")
    print("="*80)
    print("\n✅ Training complete!")
    print(f"✅ Model saved to: {config.output_dir}")
    print("\n📦 You can now use the fine-tuned model in your application!")


if __name__ == "__main__":
    main()

