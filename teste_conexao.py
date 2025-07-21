from sqlalchemy import create_engine

engine = create_engine('postgresql://neondb_owner:npg_xGpwRIb5am3S@ep-cold-queen-afdqs06g-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

conn = engine.connect()
print("✅ Conectado com sucesso:", conn)
