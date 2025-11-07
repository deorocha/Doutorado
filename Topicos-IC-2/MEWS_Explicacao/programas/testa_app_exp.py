# GERADOR DE RESPOSTAS MEWS - DETERMINÍSTICO

import json
import csv
import random
from typing import Dict, Any

def load_json_data(json_path: str = "procedimentos.json") -> Dict[str, Any]:
    """Carrega os dados do arquivo JSON"""
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except Exception as e:
        print(f"❌ Erro ao carregar JSON: {e}")
        return {"faixas_mews": []}

class JSONSearchSystem:
    def __init__(self, json_data: Dict[str, Any]):
        self.data = json_data
    
    def find_procedure(self, query: str) -> Dict[str, Any]:
        """Busca por um procedimento específico no JSON"""
        query_lower = query.lower().strip()
        
        for faixa in self.data.get("faixas_mews", []):
            for ator in faixa.get("atores", []):
                for conduta in ator.get("condutas", []):
                    for procedimento in conduta.get("procedimentos", []):
                        proc_text = procedimento.get("procedimento", "").lower()
                        
                        # Verifica se a query corresponde ao procedimento
                        if query_lower in proc_text or self.is_similar(query_lower, proc_text):
                            return {
                                "procedimento": procedimento.get("procedimento", ""),
                                "motivos": procedimento.get("motivos", {}),
                                "faixa": faixa.get("nome", ""),
                                "ator": ator.get("ator", ""),
                                "conduta": conduta.get("conduta", "")
                            }
        
        return {}
    
    def is_similar(self, query: str, procedure: str) -> bool:
        """Verifica se a query é similar ao procedimento (busca por palavras-chave)"""
        query_words = set(query.split())
        procedure_words = set(procedure.split())
        
        # Considera similar se pelo menos 2 palavras em comum
        common_words = query_words.intersection(procedure_words)
        return len(common_words) >= 2

def apply_temperature(text: str, temperature: int, original_text: str) -> str:
    """
    Aplica a temperatura ao texto, variando entre texto original e interpretado
    temperature: 0-100 (0% = texto original, 100% = máxima interpretação)
    """
    if temperature == 0:
        return text  # Texto exato da fonte
    
    # Lista de frases de transição para diferentes níveis de temperatura
    low_temp_phrases = [
        "De acordo com as diretrizes, ",
        "Conforme estabelecido no protocolo, ",
        "Baseado nas evidências, ",
        "Segundo as recomendações, "
    ]
    
    medium_temp_phrases = [
        "Do ponto de vista clínico, podemos entender que ",
        "A fundamentação fisiológica indica que ",
        "As evidências disponíveis demonstram que ",
        "Na prática clínica, observa-se que "
    ]
    
    high_temp_phrases = [
        "Analisando o contexto clínico de forma mais abrangente, ",
        "Considerando as nuances da prática hospitalar, ",
        "Em uma perspectiva integrada de cuidado, ",
        "Sintetizando o conhecimento atual, "
    ]
    
    # Escolhe frases baseadas na temperatura
    if temperature <= 33:
        phrases = low_temp_phrases
        interpretation_level = "leve"
    elif temperature <= 66:
        phrases = medium_temp_phrases
        interpretation_level = "moderada"
    else:
        phrases = high_temp_phrases
        interpretation_level = "avançada"
    
    # Aplica a interpretação baseada na temperatura
    if temperature > 0:
        # Para temperaturas baixas, mantém mais do texto original
        if temperature <= 33:
            if random.random() < 0.3:  # 30% de chance de adicionar frase introdutória
                phrase = random.choice(phrases)
                text = phrase + text.lower()
        
        # Para temperaturas médias, faz mais modificações
        elif temperature <= 66:
            if random.random() < 0.6:  # 60% de chance
                phrase = random.choice(phrases)
                text = phrase + text.lower()
            
            # Simplifica algumas estruturas complexas
            replacements = {
                "estabelece uma linha de base": "define um ponto de referência",
                "permite a detecção": "facilita a identificação",
                "sistemas homeostáticos": "mecanismos de equilíbrio do organismo",
                "deterioração": "piora do estado clínico",
                "monitorização": "acompanhamento"
            }
            
            for original, replacement in replacements.items():
                if original in text and random.random() < 0.4:
                    text = text.replace(original, replacement)
        
        # Para temperaturas altas, interpretação mais significativa
        else:
            phrase = random.choice(phrases)
            text = phrase + text.lower()
            
            # Aplica mais substituições para simplificar
            replacements = {
                "protocolos baseados na": "diretrizes da",
                "evidências clínicas": "comprovações científicas",
                "fundamento fisiológico": "base do funcionamento corporal",
                "ressuscitação volêmica": "reposição de líquidos",
                "hipoperfusão tissular": "falta de sangue nos tecidos",
                "disfunção orgânica": "problema no funcionamento dos órgãos"
            }
            
            for original, replacement in replacements.items():
                if original in text:
                    text = text.replace(original, replacement)
    
    return text

def generate_response_parts(result: Dict[str, Any], temperature: int = 0) -> Dict[str, str]:
    """Gera as partes individuais da resposta aplicando a temperatura"""
    
    motivos = result.get('motivos', {})
    
    # Aplica temperatura a cada seção individualmente
    fundamento = ""
    evidencias = ""
    riscos = ""
    impacto = ""
    
    if motivos.get('fundamento'):
        original_fundamento = motivos['fundamento']
        fundamento = apply_temperature(original_fundamento, temperature, original_fundamento)
    
    if motivos.get('evidencias'):
        original_evidencias = motivos['evidencias']
        evidencias = apply_temperature(original_evidencias, temperature, original_evidencias)
    
    if motivos.get('riscos'):
        original_riscos = motivos['riscos']
        riscos = apply_temperature(original_riscos, temperature, original_riscos)
    
    if motivos.get('impacto'):
        original_impacto = motivos['impacto']
        impacto = apply_temperature(original_impacto, temperature, original_impacto)
    
    return {
        "fundamento": fundamento,
        "evidencias": evidencias,
        "riscos": riscos,
        "impacto": impacto
    }

def generate_responses():
    """Função principal para gerar as 1000 respostas"""
    
    # Carregar dados
    json_data = load_json_data("procedimentos.json")
    search_system = JSONSearchSystem(json_data)
    
    # Entrada do usuário
    print("=== GERADOR DE RESPOSTAS MEWS - DETERMINÍSTICO ===")
    print("Este programa gera 1000 respostas variadas para a mesma pergunta")
    print("com base na temperatura de interpretação definida.\n")
    
    query = input("Digite o procedimento para consulta (ex: 'Verificar sinais vitais'): ")
    temperature = int(input("Digite a temperatura (0-100): "))
    
    # Validar temperatura
    if temperature < 0 or temperature > 100:
        print("❌ Temperatura deve estar entre 0 e 100")
        return
    
    # Buscar o procedimento
    result = search_system.find_procedure(query)
    
    if not result:
        print(f"❌ Nenhum procedimento encontrado para: '{query}'")
        print("💡 Sugestões de procedimentos:")
        print("- Verificar sinais vitais")
        print("- Realizar glicemia capilar") 
        print("- Administrar Oxigênio")
        print("- Notificar médico responsável")
        print("- Aumentar frequência de observações")
        return
    
    print(f"✅ Procedimento encontrado: {result['procedimento']}")
    print(f"🎯 Faixa MEWS: {result['faixa']} | Ator: {result['ator']}")
    print("🔄 Gerando 1000 respostas...")
    
    # Gerar 1000 respostas
    responses = []
    for i in range(1000):
        response_parts = generate_response_parts(result, temperature)
        responses.append({
            "id": i + 1,
            "pergunta": query,
            "fundamento": response_parts["fundamento"],
            "evidencias": response_parts["evidencias"],
            "riscos": response_parts["riscos"],
            "impacto": response_parts["impacto"]
        })
    
    # Salvar em CSV com ponto e vírgula como separador
    filename = f"respostas_mews_t{temperature}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'pergunta', 'fundamento', 'evidencias', 'riscos', 'impacto']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
        
        writer.writeheader()
        for response in responses:
            writer.writerow(response)
    
    print(f"\n✅ Arquivo '{filename}' gerado com sucesso!")
    print(f"📊 Total de respostas geradas: {len(responses)}")
    print(f"🌡️ Temperatura utilizada: {temperature}")
    
    # Mostrar estatísticas
    print(f"\n📈 Estatísticas das respostas:")
    fundamento_count = sum(1 for r in responses if r['fundamento'])
    evidencias_count = sum(1 for r in responses if r['evidencias'])
    riscos_count = sum(1 for r in responses if r['riscos'])
    impacto_count = sum(1 for r in responses if r['impacto'])
    
    print(f"   • Respostas com fundamento: {fundamento_count}/1000")
    print(f"   • Respostas com evidências: {evidencias_count}/1000")
    print(f"   • Respostas com riscos: {riscos_count}/1000")
    print(f"   • Respostas com impacto: {impacto_count}/1000")
    
    # Mostrar exemplo da primeira resposta
    print(f"\n📄 Exemplo da primeira resposta (ID: 1):")
    print(f"   Fundamentos: {responses[0]['fundamento'][:100]}..." if responses[0]['fundamento'] else "   Fundamentos: [Vazio]")
    print(f"   Evidências: {responses[0]['evidencias'][:100]}..." if responses[0]['evidencias'] else "   Evidências: [Vazio]")

if __name__ == "__main__":
    generate_responses()
