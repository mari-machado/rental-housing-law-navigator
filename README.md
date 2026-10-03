# Rental Housing Law Navigator

Aplicação construída para o desafio do Hack-Nation / RealPage para responder, para qualquer endereço de aluguel, quais regras se aplicam hoje e como uma mudança de lei altera esse resultado.

**Aviso importante:** este projeto é um protótipo técnico de apoio e não substitui aconselhamento jurídico profissional.

## Visão geral do projeto

O sistema está organizado em pipeline de dados + API. A lógica principal do projeto é:

- ler um corpus jurídico
- transformar documentos em regras estruturadas
- resolver a jurisdição associada ao endereço
- decidir se a regra se aplica ao caso
- comparar cenários legais e mostrar mudanças relevantes
- expor tudo por uma API para demo e validação

## Papel da IA no fluxo atual

O brief exige extração automatizada de regras a partir do corpus. A estrutura correta do projeto é:

- a IA ou agente pode ler os documentos jurídicos e produzir registros estruturados em JSON
- o código Python continua responsável pela aplicação da lógica de cobertura e pela decisão final de status
- a extração por IA é opcional e controlada por variáveis de ambiente
- quando a IA não está configurada, o sistema usa a extração heurística local em Python como fallback

Em outras palavras:

- extração do corpus: etapa de leitura/transformação, com IA opcional
- aplicação da regra ao endereço: lógica determinística em código
- auditoria: cada chamada de IA pode ser registrada em `audit.jsonl`

Isso está alinhado com as regras do desafio e com a restrição de nunca inventar regras ou citações.

## Variáveis de ambiente para IA

```bash
USE_LLM_EXTRACTION=false
OPENAI_API_KEY=seu_token
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

Se `USE_LLM_EXTRACTION` estiver habilitado e a chave estiver presente, a extração usa um endpoint compatível com OpenAI/ Azure OpenAI para transformar o texto em JSON. Se não estiver configurado, o sistema mantém o fallback em Python sem quebrar a execução.

## Arquitetura atual

```text
incial-data/
├── corpus/                # documentos jurídicos e manifest
├── data/                  # amostras de endereços e dados auxiliares
├── schema/                # schemas dos registros esperados
├── dev/                   # testes e cenários de mudança
├── submission_templates/  # modelos de saída esperados

src/
├── config.py              # caminhos e configurações gerais do projeto
├── extract.py             # extração do corpus -> rules.json
├── geocode.py             # endereço -> jurisdiction records
├── apply.py               # cobertura e status -> lookups.json
├── changes.py             # comparação de cenários -> changes.json

backend/
├── app/
│   ├── main.py            # FastAPI app com endpoints de saúde, análise e mudanças
│   └── schemas.py         # modelos da API
├── core/
│   └── config.py          # settings do backend
├── services/
│   ├── address_service.py # serviço de avaliação por endereço
│   └── rule_service.py    # carregamento de JSON de regras

outputs/
├── rules.json             # regras extraídas do corpus
├── jurisdictions.json     # endereço + jurisdição
├── lookups.json           # regras aplicáveis por endereço
├── changes.json           # cenários de mudança legais
```

## Fluxo do pipeline

```text
corpus -> extract.py -> rules.json
addresses -> geocode.py -> jurisdictions.json
rules + jurisdictions -> apply.py -> lookups.json
rules + lookups -> changes.py -> changes.json
```

## Status reais suportados

O projeto trata os seguintes status de forma explícita:

- applies
- pending
- unknown
- not_yet_effective
- superseded

A presença de `superseded` é importante para casos em que a regra local ou outra regra de precedência substitui uma regra mais ampla.

## API atual

Os endpoints principais são:

- `/health` — checagem de disponibilidade
- `/stats` — contagem de regras e endereços
- `/addresses` — listagem de amostras
- `/rules` — lista curta das regras extraídas
- `/analyze-address` — analisa um endereço e devolve o resultado de cobertura
- `/changes` — retorna indicadores de mudança legal em JSON

Todos os endpoints incluem a mensagem de segurança “not legal advice”.

## Como rodar

### 1) instalar dependências

```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
```

### 2) gerar saídas do pipeline

```bash
python src/extract.py
python src/geocode.py --data-dir incial-data/data
python src/apply.py
python src/changes.py
```

### 3) subir o backend

```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

### 4) validar a API

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/stats
```

## Restrições do desafio e alinhamento

O projeto está alinhado com as regras do brief em vários pontos:

- extração automatizada do corpus
- lógica de cobertura em código e não em LLM
- não inventa regra, citação ou status
- mantém `as_of` como parâmetro de análise
- evita que a lei seja aplicada sem dados suficientes
- retornando `unknown` quando a informação não existe
- mantém a política “not legal advice” visível ao usuário

## O que ainda precisa ser tratado como hipótese e não como conclusão jurídica

Este projeto continua sendo um protótipo para hackathon. Ele não substitui interpretação jurídica profissional e ainda depende de:

- refinamento do corpus e do matching de jurisdição
- cobertura de condições como ano de construção, número de unidades, exceções e regras locais
- validação local com o `score.py` do repositório; a pontuação oficial do desafio exige a dev key fornecida pelos organizadores
- testes de casos T6 e cenários de mudança de data

## Licença

MIT. Veja LICENSE.

