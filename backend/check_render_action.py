import httpx
import asyncio
import json

async def check_render():
    url = "https://marketmind-hz03.onrender.com/api/chat"
    payload = {"query": "Compare HDFC Flexi Cap and Parag Parikh Flexi Cap fund"}
    
    print(f"Pinging {url}...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=60)
            data = response.json()
            print("Response received.")
            print(f"Intent extracted: {data.get('debug_intent', {}).get('intent')}")
            print(f"Entities: {data.get('debug_intent', {}).get('compare_entities')}")
            
            if "system_action" in data:
                print("SUCCESS: system_action found!")
                print(json.dumps(data["system_action"], indent=2))
            else:
                print("FAILURE: system_action is missing.")
                print("Full response (trimmed):", data.get("answer")[:200] + "...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_render())
