import { NextResponse } from 'next/server';
import Groq from 'groq-sdk';

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

// Local reference to the NEXT_PUBLIC_VERCEL_URL for API loops
const getBaseUrl = () => {
    if (process.env.NODE_ENV === 'development') return 'http://localhost:3000';
    return `https://${process.env.NEXT_PUBLIC_VERCEL_URL || process.env.VERCEL_URL}`;
};

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const query = body.query;

    if (!process.env.GROQ_API_KEY) {
        throw new Error('GROQ_API_KEY missing');
    }

    // Agent interceptor: check if the user is asking about comparing or searching mutual funds.
    const tools = [
      {
        type: 'function',
        function: {
          name: 'search_instrument',
          description: 'Search for a stock or mutual fund by name/query to retrieve its ID',
          parameters: {
            type: 'object',
            properties: {
              search_query: { type: 'string', description: 'The name of the asset' },
              type: { type: 'string', enum: ['all', 'stock', 'mf'] }
            },
            required: ['search_query', 'type']
          }
        }
      },
      {
        type: 'function',
        function: {
          name: 'compare_assets',
          description: 'Compare two assets (like two mutual funds) side by side. Only use if you have the Exact scheme codes/IDs.',
          parameters: {
            type: 'object',
            properties: {
              ids: { type: 'array', items: { type: 'string' } },
              asset_type: { type: 'string', enum: ['STOCK', 'MUTUAL_FUND'] }
            },
            required: ['ids', 'asset_type']
          }
        }
      }
    ];

    const messages: any[] = [
      { role: 'system', content: 'You are an intent router. If the user asks to compare mutual funds, search for their IDs using search_instrument first, then output the comparison command via compare_assets. If the user asks a general stock question, decline tool use.' },
      { role: 'user', content: query }
    ];

    // Attempt interception
    const response = await groq.chat.completions.create({
      model: 'llama-3.1-8b-instant',
      messages,
      tools,
      tool_choice: 'auto',
      max_tokens: 1000
    });

    const choice = response.choices[0];
    
    // Check if the LLM decided to use a tool
    if (choice.message?.tool_calls) {
      const toolCall = choice.message.tool_calls[0];
      
      if (toolCall.function.name === 'search_instrument') {
         const args = JSON.parse(toolCall.function.arguments);
         const searchRes = await fetch(`${getBaseUrl()}/api/search?q=${encodeURIComponent(args.search_query)}&type=${args.type}`);
         const searchData = await searchRes.json();
         
         // LLM found the matches, let's just return a systematic UI instruction directly!
         // Or perform a second pass. For simplicity, since the prompt specifies:
         // "...return results to the LLM so it can pick correct IDs before calling compare_assets"
         messages.push(choice.message);
         messages.push({
             role: 'tool',
             tool_call_id: toolCall.id,
             name: toolCall.function.name,
             content: JSON.stringify(searchData)
         });
         
         const followUp = await groq.chat.completions.create({
             model: 'llama-3.1-8b-instant',
             messages,
             tools,
             tool_choice: 'auto'
         });
         
         const fn = followUp.choices[0].message?.tool_calls?.[0];
         if (fn && fn.function.name === 'compare_assets') {
            const finalArgs = JSON.parse(fn.function.arguments);
            return NextResponse.json({
                answer: `I have found the assets you mentioned. I am launching the comparison dashboard now.`,
                system_action: {
                    type: 'COMPARE',
                    ids: finalArgs.ids,
                    asset_type: finalArgs.asset_type
                }
            });
         }
      } else if (toolCall.function.name === 'compare_assets') {
         const args = JSON.parse(toolCall.function.arguments);
         return NextResponse.json({
            answer: `Launching the comparison view for your requested assets.`,
            system_action: {
                type: 'COMPARE',
                ids: args.ids,
                asset_type: args.asset_type
            }
         });
      }
    }

    // If no tools matched, proxy to the FastAPI backend!
    const TARGET = process.env.NODE_ENV === 'development'
      ? 'http://127.0.0.1:8000/api/chat'
      : `${process.env.NEXT_PUBLIC_API_URL}/api/chat`;
    
    const proxyRes = await fetch(TARGET, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!proxyRes.ok) return NextResponse.json({ error: 'Upstream Error' }, { status: proxyRes.status });
    const data = await proxyRes.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Chat Proxy/Tool Error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
