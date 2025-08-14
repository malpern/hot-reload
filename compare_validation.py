#!/usr/bin/env python3
"""
Compare TCP validation output with --check output
"""
import json
from kanata_parser import cfg

def test_validation():
    invalid_config = """(defsrc esc 1 2 3

(deflayer default
  esc 1 2 3"""
    
    print("=== TCP Validation Output ===")
    try:
        # This simulates what TCP validation would return
        errors, warnings = cfg.validate_config_str(invalid_config)
        
        result = {
            "ValidationResult": {
                "success": len(errors) == 0,
                "errors": [
                    {
                        "line": err.line,
                        "column": err.column,
                        "message": err.message,
                        "severity": "error" if err.severity == cfg.DiagnosticSeverity.Error else "warning",
                        "category": err.category.name.lower(),
                        "file": err.file,
                        "help_text": err.help_text
                    } for err in errors
                ],
                "warnings": [
                    {
                        "line": warn.line,
                        "column": warn.column,
                        "message": warn.message,
                        "severity": "warning",
                        "category": warn.category.name.lower(),
                        "file": warn.file,
                        "help_text": warn.help_text
                    } for warn in warnings
                ],
                "error_count": len(errors),
                "warning_count": len(warnings)
            }
        }
        
        print(json.dumps(result, indent=2))
        
    except ImportError:
        print("Cannot import kanata_parser directly - would need to run via TCP")
        print("But TCP validation would provide structured JSON like:")
        print(json.dumps({
            "ValidationResult": {
                "success": False,
                "errors": [{
                    "line": 3,
                    "column": 1,
                    "message": "Unclosed opening parenthesis",
                    "severity": "error",
                    "category": "syntax",
                    "file": "configuration",
                    "help_text": "Check parentheses balance"
                }],
                "warnings": [],
                "error_count": 1,
                "warning_count": 0
            }
        }, indent=2))

if __name__ == "__main__":
    test_validation()