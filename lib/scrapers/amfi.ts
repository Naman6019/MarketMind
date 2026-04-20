import { supabase } from '../supabase';

export async function syncAMFIData() {
  console.log('Fetching AMFI Data...');
  try {
    const response = await fetch('https://www.amfiindia.com/spages/NAVAll.txt');
    if (!response.ok) {
      throw new Error(`AMFI API Error: ${response.status}`);
    }
    
    const textData = await response.text();
    const lines = textData.split('\n');
    
    const updates = [];
    let currentCategory = 'Unknown Category';
    let currentFundHouse = 'Unknown Fund House';
    
    // Process line by line
    for (const line of lines) {
      const trimmed = line.trim();
      
      // Empty line -> section transition
      if (!trimmed) continue;
      
      // If line has no semicolon, it's usually a category / sub-category header
      if (!trimmed.includes(';')) {
        // e.g. "Open Ended Schemes ( Money Market Scheme )"
        currentCategory = trimmed;
        
        // Sometimes it's a AMC name like "Aditya Birla Sun Life Mutual Fund"
        if (trimmed.toLowerCase().includes('mutual fund')) {
           currentFundHouse = trimmed;
        }
        continue;
      }
      
      // Data line format: Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
      const parts = trimmed.split(';');
      if (parts.length >= 6) {
        const schemeCode = parseInt(parts[0], 10);
        if (isNaN(schemeCode)) continue; // skip header line or invalid lines
        
        const schemeName = parts[3];
        const nav = parseFloat(parts[4]);
        const dateStr = parts[5]; // Format: dd-MMM-yyyy
        
        if (isNaN(nav) || !dateStr) continue;
        
        let navDate = null;
        try {
           const [d, mStr, y] = dateStr.split('-');
           const m = new Date(`${mStr} 1 2000`).getMonth(); 
           navDate = new Date(Date.UTC(parseInt(y), m, parseInt(d))).toISOString();
        } catch {
           navDate = new Date().toISOString();
        }
        
        // Note: For a real app we would want better category parsing, but for now we'll put the whole header in Category
        // and infer sub-category. AMFI's structure is somewhat inconsistent.
        updates.push({
          scheme_code: schemeCode,
          scheme_name: schemeName,
          fund_house: currentFundHouse,
          category: currentCategory.split('(')[0]?.trim() || 'General',
          sub_category: currentCategory.split('(')[1]?.replace(')','')?.trim() || 'General',
          nav: nav,
          nav_date: navDate,
          updated_at: new Date().toISOString()
        });
      }
    }
    
    console.log(`Parsed ${updates.length} schemes. Beginning upsert to Supabase...`);
    
    // Batch upsert to avoid Supabase limits (doing 1000 at a time)
    const batchSize = 1000;
    let successCount = 0;
    
    for (let i = 0; i < updates.length; i += batchSize) {
      const batch = updates.slice(i, i + batchSize);
      
      const { error } = await supabase
        .from('mutual_funds')
        .upsert(batch, { onConflict: 'scheme_code' });
        
      if (error) {
        console.error('Supabase Upsert Error:', error);
      } else {
        successCount += batch.length;
      }
    }
    
    return { success: true, count: successCount };
    
  } catch (error) {
    console.error('AMFI Scraper Failed:', error);
    return { success: false, error: (error as Error).message };
  }
}
