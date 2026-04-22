import httpx
import asyncio
import json

async def main():
    query = {"query": "Compare HDFC Flexi Cap and Parag Parikh Flexi Cap fund"}
    
    # Test local
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("http://localhost:8000/api/chat", json=query, timeout=10)
            print("LOCAL BACKEND:")
            data = res.json()
            if "system_action" in data:
                print("  HAS system_action!", data["system_action"])
            else:
                print("  MISSING system_action")
    except Exception as e:
        print("LOCAL BACKEND: FAILED", str(e))
        
    # Test remote
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post("https://marketmind-hz03.onrender.com/api/chat", json=query, timeout=60)
            print("REMOTE BACKEND:")
            data = res.json()
            if "system_action" in data:
                print("  HAS system_action!", data["system_action"])
            else:
                print("  MISSING system_action")
    except Exception as e:
        print("REMOTE BACKEND: FAILED", str(e))

if __name__ == "__main__":
    asyncio.run(main())
