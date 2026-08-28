# Contexto Arquitetural — Analytics

## Objetivo

Este servico Python/FastAPI complementa o Controle de Merenda Escolar com rotinas analiticas batch. Ele nao substitui a API Java e nao participa da fila.

## Responsabilidades

- Receber dados agregados da API Java.
- Calcular previsao de demanda.
- Calcular ajuste sugerido de producao.
- Classificar risco estatistico de desperdicio.
- Retornar JSON estruturado para a API Java persistir e combinar com relatorios gerenciais.

## Fora de Escopo

- Validacao de consumo na fila.
- Persistencia transacional do dominio.
- Reconhecimento facial em producao.
- Armazenamento de fotos, biometria, matriculas ou dados pessoais.
- Chamada direta ao Gemini nesta fase.

## Estrategia de Evolucao

A primeira versao usa um baseline estatistico explicavel e sem dependencias pesadas. `pandas` e `scikit-learn` podem entrar depois, quando houver historico suficiente para previsoes melhores.

O contrato HTTP deve permanecer simples para o backend Java conseguir trocar entre adapter fake/local e adapter Python HTTP sem alterar o dashboard.
