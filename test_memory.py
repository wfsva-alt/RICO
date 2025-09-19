#!/usr/bin/env python3
"""
Test script to verify Redis connection and memory functionality
"""
import os
import json
import sys
sys.path.append('.')

from bot.memory_manager import MemoryManager
from bot.tools import tool_add_core_memory, tool_get_core_memory, CREATOR_IDS

def test_redis_connection():
    """Test if Redis is accessible"""
    print("Testing Redis connection...")
    try:
        memory_manager = MemoryManager()
        if memory_manager.r is None:
            print("❌ Redis not configured (USE_REDIS=false or Redis unavailable)")
            return False
        
        # Test basic Redis operations
        memory_manager.r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def test_core_memory():
    """Test core memory functionality"""
    print("\nTesting core memory functionality...")
    try:
        # Test adding core memory
        test_data = {
            "user_id": list(CREATOR_IDS)[0],  # Use first creator ID
            "title": "Test Creator",
            "content": "This is a test core memory entry"
        }
        
        result = tool_add_core_memory(json.dumps(test_data))
        print(f"Add core memory result: {result}")
        
        # Test retrieving core memory
        get_data = {"user_id": list(CREATOR_IDS)[0]}
        core_memory = tool_get_core_memory(json.dumps(get_data))
        print(f"Retrieved core memory: {core_memory}")
        
        # Parse and display the memory
        try:
            memory_data = json.loads(core_memory)
            if isinstance(memory_data, list):
                print(f"✅ Core memory contains {len(memory_data)} entries")
                for i, entry in enumerate(memory_data):
                    print(f"  Entry {i+1}: {entry.get('title', 'No title')} - {entry.get('content', 'No content')[:50]}...")
            else:
                print(f"✅ Core memory: {memory_data}")
        except json.JSONDecodeError:
            print(f"✅ Core memory (raw): {core_memory}")
        
        return True
    except Exception as e:
        print(f"❌ Core memory test failed: {e}")
        return False

def main():
    print("RICO Discord Bot Memory System Test")
    print("=" * 40)
    
    # Check environment variables
    print(f"USE_REDIS: {os.getenv('USE_REDIS', 'false')}")
    print(f"REDIS_URL: {os.getenv('REDIS_URL', 'redis://localhost:6379/0')}")
    print(f"CREATOR_IDS: {CREATOR_IDS}")
    
    # Test Redis connection
    redis_ok = test_redis_connection()
    
    if redis_ok:
        # Test core memory
        memory_ok = test_core_memory()
        
        if memory_ok:
            print("\n✅ All tests passed! Memory system is working correctly.")
        else:
            print("\n❌ Memory system tests failed.")
    else:
        print("\n❌ Redis connection failed. Please check your Redis setup.")
        print("\nTo fix this:")
        print("1. Make sure Redis is running: docker-compose up redis -d")
        print("2. Set USE_REDIS=true in your .env file")
        print("3. Verify REDIS_URL is correct")

if __name__ == "__main__":
    main()
