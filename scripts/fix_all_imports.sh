#!/bin/bash

# Fix all import issues in CORE codebase
echo "Fixing import issues in CORE..."

cd /opt/dev/CORE

# Fix 1: Replace body.services.knowledge_service with services.knowledge_service
echo "Fixing KnowledgeService imports..."
find . -name "*.py" -type f | while read file; do
    if grep -q "from body.services.knowledge_service import" "$file"; then
        sed -i 's/from body\.services\.knowledge_service import/from services.knowledge_service import/g' "$file"
        echo "  Fixed: $file"
    fi
done

# Fix 2: Fix test files importing from 'core' module
echo "Fixing 'core' module imports in tests..."
find tests/ -name "*.py" -type f | while read file; do
    # Fix core.agents imports
    if grep -q "from core\.agents" "$file"; then
        sed -i 's/from core\.agents/from will.agents/g' "$file"
        echo "  Fixed agents import in: $file"
    fi
    if grep -q "import core\.agents" "$file"; then
        sed -i 's/import core\.agents/import will.agents/g' "$file"
        echo "  Fixed agents import in: $file"
    fi

    # Fix core.actions imports
    if grep -q "from core\.actions" "$file"; then
        sed -i 's/from core\.actions/from will.orchestration.actions/g' "$file"
        echo "  Fixed actions import in: $file"
    fi

    # Fix generic core imports
    if grep -q "from core\." "$file"; then
        sed -i 's/from core\./from will.orchestration./g' "$file"
        echo "  Fixed core import in: $file"
    fi
    if grep -q "import core\." "$file"; then
        sed -i 's/import core\./import will.orchestration./g' "$file"
        echo "  Fixed core import in: $file"
    fi
done

# Fix 3: Fix features.governance imports that should be mind.governance
echo "Fixing features.governance imports..."
find tests/ -name "*.py" -type f | while read file; do
    if grep -q "import features\.governance" "$file"; then
        sed -i 's/import features\.governance/import mind.governance/g' "$file"
        echo "  Fixed governance import in: $file"
    fi
    if grep -q "from features\.governance" "$file"; then
        sed -i 's/from features\.governance/from mind.governance/g' "$file"
        echo "  Fixed governance import in: $file"
    fi
done

# Fix 4: Apply the specific fixed files
echo "Applying specific file fixes..."

# Copy fixed drift_service.py
if [ -f /mnt/user-data/outputs/drift_service.py ]; then
    cp /mnt/user-data/outputs/drift_service.py src/features/introspection/drift_service.py
    echo "  Applied fix to drift_service.py"
fi

# Copy fixed audit_unassigned_capabilities.py
if [ -f /mnt/user-data/outputs/audit_unassigned_capabilities.py ]; then
    cp /mnt/user-data/outputs/audit_unassigned_capabilities.py src/features/introspection/audit_unassigned_capabilities.py
    echo "  Applied fix to audit_unassigned_capabilities.py"
fi

# Copy fixed policy_loader.py
if [ -f /mnt/user-data/outputs/policy_loader.py ]; then
    cp /mnt/user-data/outputs/policy_loader.py src/mind/governance/policy_loader.py
    echo "  Applied fix to policy_loader.py"
fi

echo "All import fixes applied!"
echo ""
echo "Run 'pytest' to verify the fixes."
