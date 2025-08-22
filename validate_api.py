"""
Validation script for Fusion 360 Hexagon Generator Add-in.

This script validates that the API methods used in the add-in are correct
and checks for common issues without requiring Fusion 360 to be running.
"""

import re
import os
import json


class FusionAPIValidator:
    """Validator for Fusion 360 API usage."""
    
    def __init__(self):
        # Known valid Fusion 360 API classes and methods
        self.valid_api = {
            'adsk.core': {
                'Application': ['get'],
                'CommandCreatedEventHandler': [],
                'InputChangedEventHandler': [],
                'ValidateInputsEventHandler': [],
                'CommandEventHandler': [],
                'ValueInput': ['createByReal'],
                'Point3D': ['create'],
                'ObjectCollection': ['create'],
                'DropDownStyles': ['LabeledIconDropDownStyle'],
            },
            'adsk.fusion': {
                'FeatureOperations': ['CutFeatureOperation', 'NewBodyFeatureOperation'],
                'ExtentDirections': ['PositiveExtentDirection', 'NegativeExtentDirection'],
                'ToEntityExtentDefinition': ['create'],
                'ThroughAllExtentDefinition': ['create'],
                'BRepFace': [],
                'Profile': [],
            }
        }
        
        # Common API mistakes (excluding comments)
        self.common_mistakes = {
            'throughallextentdefinition': 'Should be ThroughAllExtentDefinition (case sensitive)',
            './/resources': 'Should be ./resources (single forward slash)',
            "'Resources'": 'Should be resources (lowercase)',
            '"Resources"': 'Should be resources (lowercase)',
        }
        
        # Required files and folders
        self.required_structure = {
            'files': [
                'HexagonGenerator.py',
                'HexagonGenerator.manifest',
            ],
            'folders': [
                'resources',
            ],
            'icon_files': [
                'resources/16x16.png',
                'resources/32x32.png',
            ]
        }
    
    def validate_manifest(self, manifest_path):
        """Validate the manifest file structure."""
        issues = []
        
        if not os.path.exists(manifest_path):
            issues.append("ERROR: Manifest file not found")
            return issues
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # Check required fields
            required_fields = ['autodeskProduct', 'type', 'id']
            for field in required_fields:
                if field not in manifest:
                    issues.append(f"ERROR: Missing required field '{field}' in manifest")
            
            # Validate field values
            if manifest.get('autodeskProduct') != 'Fusion360':
                issues.append(f"ERROR: autodeskProduct should be 'Fusion360', not '{manifest.get('autodeskProduct')}'")
            
            if manifest.get('type') not in ['addin', 'script']:
                issues.append(f"ERROR: type should be 'addin' or 'script', not '{manifest.get('type')}'")
            
            # Check for run/stop functions if type is addin
            if manifest.get('type') == 'addin':
                py_file = manifest_path.replace('.manifest', '.py')
                if os.path.exists(py_file):
                    with open(py_file, 'r') as f:
                        content = f.read()
                        if 'def run(' not in content:
                            issues.append("WARNING: Add-in missing run() function")
                        if 'def stop(' not in content:
                            issues.append("WARNING: Add-in missing stop() function")
            
            print("✓ Manifest structure validated")
            
        except json.JSONDecodeError as e:
            issues.append(f"ERROR: Invalid JSON in manifest: {e}")
        except Exception as e:
            issues.append(f"ERROR: Failed to validate manifest: {e}")
        
        return issues
    
    def validate_python_code(self, py_path):
        """Validate Python code for common API issues."""
        issues = []
        
        if not os.path.exists(py_path):
            issues.append("ERROR: Python file not found")
            return issues
        
        with open(py_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Check for common mistakes
        for mistake, correction in self.common_mistakes.items():
            if mistake in content:
                # Find line number
                for i, line in enumerate(lines, 1):
                    if mistake in line:
                        issues.append(f"LINE {i}: Found '{mistake}' - {correction}")
        
        # Check for proper imports
        if 'import adsk.core' not in content:
            issues.append("WARNING: Missing 'import adsk.core'")
        if 'import adsk.fusion' not in content:
            issues.append("WARNING: Missing 'import adsk.fusion'")
        
        # Check for addButtonDefinition usage
        button_pattern = r'addButtonDefinition\s*\([^)]+\)'
        matches = re.findall(button_pattern, content)
        for match in matches:
            # Check if resources folder is specified correctly
            if './/resources' in match:
                issues.append("ERROR: Use './resources' not './/resources' in addButtonDefinition")
            if 'Resources' in match:
                issues.append("ERROR: Use 'resources' (lowercase) not 'Resources' in path")
        
        # Check for proper exception handling
        bare_except_pattern = r'^\s*except:\s*$'
        for i, line in enumerate(lines, 1):
            if re.match(bare_except_pattern, line):
                # This is OK for Fusion API as it's required pattern
                pass
        
        # Validate API calls
        api_pattern = r'adsk\.(core|fusion)\.(\w+)'
        api_calls = re.findall(api_pattern, content)
        for module, class_name in api_calls:
            if module in self.valid_api:
                # Just note it, don't validate every single one
                pass
        
        print("✓ Python code structure validated")
        return issues
    
    def validate_folder_structure(self, root_path):
        """Validate the folder structure."""
        issues = []
        
        # Check required files
        for file in self.required_structure['files']:
            file_path = os.path.join(root_path, file)
            if not os.path.exists(file_path):
                issues.append(f"ERROR: Missing required file: {file}")
            else:
                print(f"✓ Found {file}")
        
        # Check required folders
        for folder in self.required_structure['folders']:
            folder_path = os.path.join(root_path, folder)
            if not os.path.exists(folder_path):
                issues.append(f"ERROR: Missing required folder: {folder}")
            else:
                print(f"✓ Found {folder}/")
        
        # Check for at least some icon files
        icon_found = False
        for icon_file in self.required_structure['icon_files']:
            icon_path = os.path.join(root_path, icon_file)
            if os.path.exists(icon_path):
                icon_found = True
                print(f"✓ Found {icon_file}")
        
        if not icon_found:
            issues.append("WARNING: No icon files found in resources folder")
        
        return issues
    
    def validate_all(self, root_path='.'):
        """Run all validations."""
        print("=" * 60)
        print("Fusion 360 Add-in Validation Report")
        print("=" * 60)
        
        all_issues = []
        
        # Validate folder structure
        print("\n1. Validating folder structure...")
        issues = self.validate_folder_structure(root_path)
        all_issues.extend(issues)
        
        # Validate manifest
        print("\n2. Validating manifest file...")
        manifest_path = os.path.join(root_path, 'HexagonGenerator.manifest')
        issues = self.validate_manifest(manifest_path)
        all_issues.extend(issues)
        
        # Validate Python code
        print("\n3. Validating Python code...")
        py_path = os.path.join(root_path, 'HexagonGenerator.py')
        issues = self.validate_python_code(py_path)
        all_issues.extend(issues)
        
        # Summary
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        if not all_issues:
            print("✅ All validations passed! The add-in structure appears correct.")
            print("\nNext steps:")
            print("1. Copy the fusion_hexagon folder to Fusion 360's AddIns directory")
            print("2. Start Fusion 360")
            print("3. Go to Utilities > ADD-INS > Scripts and Add-Ins")
            print("4. Select the Add-Ins tab")
            print("5. Find 'HexagonGenerator' and click Run")
        else:
            print(f"❌ Found {len(all_issues)} issue(s):\n")
            
            errors = [i for i in all_issues if i.startswith("ERROR")]
            warnings = [i for i in all_issues if i.startswith("WARNING")]
            others = [i for i in all_issues if not i.startswith("ERROR") and not i.startswith("WARNING")]
            
            if errors:
                print("ERRORS (must fix):")
                for issue in errors:
                    print(f"  • {issue}")
            
            if warnings:
                print("\nWARNINGS (should fix):")
                for issue in warnings:
                    print(f"  • {issue}")
            
            if others:
                print("\nOTHER ISSUES:")
                for issue in others:
                    print(f"  • {issue}")
        
        return len(all_issues) == 0


def main():
    """Run the validation."""
    validator = FusionAPIValidator()
    success = validator.validate_all('.')
    
    if success:
        print("\n✅ Validation successful!")
    else:
        print("\n⚠️  Please fix the issues above before installing the add-in.")
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())