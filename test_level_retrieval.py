#!/usr/bin/env python3

import sqlite3
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import get_levels

def test_level_retrieval():
    """Test the level retrieval functionality"""
    print("🧪 Testing Level Retrieval")
    print("=" * 50)
    
    try:
        # Test the get_levels function directly
        user_id = 'default_user'
        levels = get_levels(user_id)
        
        print(f"✅ Function executed successfully")
        print(f"📊 Retrieved levels: {levels}")
        
        # Check if levels are properly structured
        if isinstance(levels, dict):
            print("✅ Levels is a dictionary")
            
            for index_type in ['BANK_NIFTY', 'NIFTY_50']:
                if index_type in levels:
                    print(f"✅ {index_type} section exists")
                    for level_num in [1, 2, 3]:
                        if levels[index_type][level_num] is not None:
                            level_data = levels[index_type][level_num]
                            print(f"  Level {level_num}: {level_data}")
                        else:
                            print(f"  Level {level_num}: None")
                else:
                    print(f"❌ {index_type} section missing")
        else:
            print(f"❌ Levels is not a dictionary: {type(levels)}")
            
    except Exception as e:
        print(f"❌ Error testing level retrieval: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_level_retrieval()

