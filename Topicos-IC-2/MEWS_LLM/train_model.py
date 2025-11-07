# train_model.py - Executa UMA VEZ para criar e salvar o modelo
import json
from pathlib import Path
from mews_model import MEWSModel, save_model

def main():
    PROJECT_ROOT = Path(__file__).parent
    
    # Carrega JSON
    json_path = PROJECT_ROOT / "arquivos" / "procedimentos.json"
    
    if not json_path.exists():
        print(f"❌ Arquivo JSON não encontrado: {json_path}")
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        print("📁 JSON carregado com sucesso")
        
    except Exception as e:
        print(f"❌ Erro ao carregar JSON: {e}")
        return
    
    # Cria e treina modelo
    print("🔄 Criando e treinando modelo...")
    try:
        model = MEWSModel()
        model.train(json_data)
        
        # Salva modelo
        model_path = PROJECT_ROOT / "models" / "mews_model.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        save_model(model, model_path)
        
        print(f"✅ Modelo salvo com sucesso!")
        print(f"📊 Estatísticas:")
        print(f"   - Documentos processados: {len(model.data)}")
        print(f"   - Arquivo do modelo: {model_path}")
        
    except Exception as e:
        print(f"❌ Erro no treinamento: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando treinamento do modelo MEWS...")
    main()
    print("🎯 Treinamento concluído!")
