import os
import psycopg
from dotenv import load_dotenv

load_dotenv() # le oq ta em .env

host = os.getenv("DB_HOST")
porta = os.getenv("DB_PORT")
banco = os.getenv("DB_NAME")
usuario = os.getenv("DB_USER")
senha = os.getenv("DB_PASSWORD") 

#.env
#      ↓
#os.getenv()
#      ↓
#Variáveis Python

def conectar():
    try:
        conexao = psycopg.connect(
            host=host,
            port=porta,
            dbname=banco,
            user=usuario,
            password=senha
        )

        print("Conexão realizada com sucesso!")
        return conexao

    except Exception as e:
        print(f"Erro ao conectar ao banco: {e}")
        return None