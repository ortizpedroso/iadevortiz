# Agentes da PKF

Os agentes vivem em `pkf/agents/prompts.py`. O `Router` instancia cada um com um subconjunto de ferramentas.

## Agentes de domínio

| Agente | Papel | Ferramentas |
|---|---|---|
| `architect` | Desenha o sistema e fecha a spec | leitura, busca, specs |
| `frontend` | UI, componentes, CSS/HTML | leitura, escrita, terminal, specs |
| `backend` | APIs, dados, autenticação | leitura, escrita, terminal, specs |
| `logic` | Algoritmos e regras de negócio | leitura, escrita, terminal, specs |
| `reviewer` | Review contra a spec | leitura, busca, `save_review` |
| `tester` | Testes e execução | leitura, escrita, terminal |
| `generalista` | Perguntas fora de implementação | leitura do workspace |

## Ciclo

1. Pedido de recurso ou `/spec` → entrevista e `save_spec`
2. `/build` → `get_spec` + implementação com `write_file`
3. Mudança depois do build → atualiza a spec antes de mexer no código
4. `/review` ou pedido de revisão → `reviewer` + `save_review`

Estado persistido em `.pkf/session.json`.

## Memória

A cada 12 mensagens de texto o agente resume o trecho, registra um agente `memoria_*` no roteador e grava o índice em `.pkf/memory/index.json`. Perguntas seguintes podem voltar a esse especialista por sobreposição de termos.
