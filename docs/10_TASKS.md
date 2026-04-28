# Ongoing Tasks & Limitations

## Known Limitations (Do Not Break)
- **Portfolio Overlap**: Logic exists in the canvas components but depends on real-time AMFI data availability. Do not remove this logic.
- **Stock Comparison**: Currently, the Canvas is optimized for Mutual Fund (MF) comparison. Stock-to-stock comparison is in active development.
- **News Latency**: News fetching relies on Google News RSS.

## Future Improvements
- Add a dedicated backend `/api/quant` endpoint.
- Move benchmark fetching fully server-side.
- Cache live quotes during market hours inside Supabase.
