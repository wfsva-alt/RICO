# RICO Redis Memory Schema

## CoreMemory
- Key: `core:memory`
- Type: String
- Value: JSON string (permanent persona/system data)

## UserMemory
- Key: `user:<user_id>:memory`
- Type: Hash
- Fields:
  - `traits`: JSON array
  - `preferences`: JSON object
  - `history`: JSON array

## GeneralMemory (RAG)
- Key: RediSearch index: `idx:general_memory`
- Each entry:
  - `content`: Text
  - `metadata`: JSON string
  - `vector`: VECTOR (FLOAT32, 1536 dims for OpenAI Ada)
- Use FT.CREATE with VECTOR field for semantic search.

## ChannelContext
- Key: `history:<channel_id>`
- Type: List
- Value: Each item is a JSON string (message, metadata)
- Vector index: `idx:channel_ctx:<channel_id>`

## Example RediSearch FT.CREATE (vector):
```
docker exec -it redis-stack redis-cli "FT.CREATE idx:general_memory ON HASH PREFIX 1 general:memory: SCHEMA content TEXT metadata TEXT vector VECTOR HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE"


```

## Notes
- All user/general/channel data is JSON-serialized.
- Use RediSearch for all vector search (RAG).
- Fallback to SQLite: tables for user_memory, general_memory, channel_context.
