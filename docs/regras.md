# 🏆 Mecathron – Hackathon Mecatrônico 2025

> Um Hackathon Mecatrônico focado no desenvolvimento de Inteligência Artificial e controle autônomo para robôs.

## 📅 Datas e Horários

| Tópico | Detalhe |
| :--- | :--- |
| **Dia do Evento** | 29 de Novembro de 2025 |
| **Local** | IFSC Campus Florianópolis |
| **Início do Evento** | 08h00 |
| **Formação de Equipes** | 08h30 |
| **Início das Provas** | 16h00 |

## I. 💡 Visão Geral e Formato Geral

| Tópico | Definição |
| :--- | :--- |
| **Nome do Evento** | Mecathron – Hackathon Mecatrônico 2025 |
| **Participação** | As equipes podem participar de um ou de ambos os desafios: **Pac-Man** e **Rocket League**. |
| **Arquitetura básica de funcionamento** | Um servidor da organização disponibilizará dados de coordenadas e ângulos de robôs e da bola (no caso do desafio Rocket-League) via WebSocket através de uma API. Cada robô também terá uma API e disponibilizará dados de sensores, assim como receberá comando para seus motores, também via WebSoocket. Os participantes devem se preocupar com os algoritmos de movimentação autônoma dos robôs, apenas.|

## II. Desafio 1: 🕹️ PAC-MAN

Este desafio combina desenvolvimento de IA (para os Fantasmas) com pilotagem humana (para o Pac-Man).

### Sistema de Pontuação e Vitória (Pac-Man Piloto)

| Ação | Pontos | Critério de Vitória (Piloto) |
| :--- | :--- | :--- |
| Coleta de bandeira | +1 Ponto | O Piloto com a **maior pontuação** em sua única rodada de 3 minutos. |
| Coleta de bandeira Power | +5 Pontos e a possibilidade de caçar fantasmas | |
| Captura de Fantasma | +10 Pontos | |
| Ser Capturado | -5 Pontos (e retorno ao ponto inicial) | |

### Sistema de Pontuação e Vitória (Fantasma - Equipe)

| Ação | Pontos | Critério de Vitória (Equipe Fantasma) |
| :--- | :--- | :--- |
| Capturar o Pac-Man | +N Pontos = tempo (em segundos) restantes para o término da rodada | A Equipe cujo robô Fantasma somar a **maior pontuação acumulada** no total das rodadas do evento. |
| Ser Capturado | Perda temporária do Fantasma – 10 segundos | |

## III. Desafio 2: ⚽ ROCKET LEAGUE

Este desafio foca no desenvolvimento de estratégia e controle **totalmente autônomos** para um jogo de futebol.

### A. Estrutura e Formato

* **Arena:** Campo de futebol miniaturizado.
* **Robôs:** 2 robôs (um por equipe) e 1 bola.
* **Controle:** Robôs devem ser **totalmente autônomos**.
* **Formato:** Jogos eliminatórios (mata-mata), ajustáveis conforme o número de inscritos.
* **Duração:** Jogos de 5 minutos.

### B. Sistema de Pontuação e Desempate

| Ação/Regra | Pontos/Regra |
| :--- | :--- |
| **Gol** | 1 Ponto. |
| **Vitória** | A equipe com o maior número de gols ao final dos 5 minutos. |
| **Empate (Prorrogação)** | **Gol de Ouro** (_Golden Goal_). O primeiro gol marcado na prorrogação define o vencedor. |
| **Empate (Limite)** | Se o Gol de Ouro não ocorrer em 2 minutos de prorrogação, a partida será decidida por um sistema de Pênaltis (a ser detalhado). |

## IV. ⚙️ ESPECIFICAÇÕES TÉCNICAS E DE HARDWARE



### A. Plataforma e Hardware

* **Robôs Fornecidos:** Os robôs (chassi, motores, atuadores) para ambos os desafios serão **fornecidos montados e prontos** pela organização.
* **Restrições de Hardware:** As equipes estão **estritamente proibidas** de realizar modificações físicas nos robôs, incluindo alteração ou adição de componentes, motores, baterias ou sensores.
* **Devolução:** Os robôs são propriedade da organização e devem ser devolvidos intactos ao final do evento.

### B. Desenvolvimento de Software

* **Linguagem de Programação:** Não há restrição de linguagem. É incentivado o uso de Python, mas **qualquer linguagem compatível com o protocolo WebSocket** é permitida.
* **Execução do Algoritmo:** O software da equipe deverá ser executado em um **computador da própria equipe**.
* **API de Comunicação:**
    * Cada robô terá uma API para comunicação.
    * Esta API será o único ponto de contato para disponibilizar dados de sensores do robô e responder a comandos de ação (controle de motorização).
    * O **Formato de Mensagens da API (JSON)** será detalhado na próxima atualização destas regras

## V. ⚠️ REGRAS DE CONDUTA E PENALIDADES

| Ocorrência | Penalidade (Sugestão) |
| :--- | :--- |
| Colisão Agressiva/Fora de Jogo | Em Rocket League, contato físico excessivamente agressivo ou intencional resultará em advertência ou desclassificação da partida. |
| Interferência (Pac-Man) | O Pac-Man (piloto) que sair da área de jogo intencionalmente ou colidir repetidamente com paredes poderá ser penalizado com perda de tempo ou desclassificação da rodada. |
| **Modificação de Hardware** | **Qualquer violação das restrições de hardware resultará em desclassificação imediata da equipe do evento**. |

## VI. 🔗 Desenhos e fotos

* Fotos e desenhos dos robôs com suas dimensões, bem como das arenas - serão adicionados em uma atualização deste arquivo
