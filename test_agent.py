#!/usr/bin/env python3
"""
Test script to verify agent functionality
"""
import asyncio
import sys
sys.path.append('.')

from bot.agent import Agent
from bot.tools import CREATOR_IDS

async def test_agent():
    """Test the agent with a simple memory task"""
    print("Testing RICO Agent...")
    print("=" * 30)
    
    agent = Agent()
    
    # Test with a creator ID
    test_user_id = list(CREATOR_IDS)[0]
    
    # Test query that should trigger memory tools
    test_query = "add a core memory about your creators, 1st creator: tuxsharx(aka tux) description: created you, known for his AI jailbreaking skills, tech skills, and known in the street for his impeccable street cred. 2nd creator: wsfva description: create you, known for his AI and tech skills, also known in the streets for the nigga who made it out the hood"
    
    print(f"Test User ID: {test_user_id}")
    print(f"Test Query: {test_query[:100]}...")
    print()
    
    try:
        result = await agent.run_agent(test_query, user_id=test_user_id)
        print("Agent Response:")
        print("-" * 20)
        print(result)
        print("-" * 20)
        
        # Test retrieving the memory
        print("\nTesting memory retrieval...")
        retrieve_query = "retrieve the core memory please"
        result2 = await agent.run_agent(retrieve_query, user_id=test_user_id)
        print("Retrieval Response:")
        print("-" * 20)
        print(result2)
        print("-" * 20)
        
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
