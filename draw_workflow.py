#!/usr/bin/env python
"""
Generate workflow visualization

Usage: python draw_workflow.py [output_path]
"""

import sys
from src.utils import draw_workflow_graph


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "workflow_graph.png"
    
    print(f"Generating workflow graph: {output}")
    
    result = draw_workflow_graph(output)
    
    if result:
        import os
        print(f"✓ Success! Saved to: {os.path.abspath(result)}")
    else:
        print("✗ Failed to generate graph")
        sys.exit(1)


if __name__ == "__main__":
    main()

