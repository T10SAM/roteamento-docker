# Rede Virtual com Contêiners

Laboratório de roteamento dinâmico com FRRouting (FRR) rodando em containers Docker, simulando uma topologia de 5 roteadores.

## Topologia
Seguindo a ideia de uma topologia em anel, é formada por 5 roteadores conectados por link ponto a ponto e com dois links extras de redundância. Conforme a imagem abaixo:
![Topologia do Projeto](./topologia/topologia.png)

Lista de endereço IP de cada roteador:

| Roteador | Endereços IP | Conectado aos Roteadores |

| **R1** | `192.168.5.2`, `192.168.9.3`, `192.100.1.2` | R2, R5, R3 |

| **R2** | `192.168.5.3`, `192.168.6.2`, `192.100.2.3` | R1, R3, R5 |

| **R3** | `192.168.6.3`, `192.168.7.2`, `192.100.1.3` | R2, R4, R1 |

| **R4** | `192.168.7.3`, `192.168.8.2` | R3, R5 |

| **R5** | `192.168.8.3`, `192.168.9.2`, `192.100.2.2` | R4, R1, R2 |


## Pré-requisitos
- Docker Desktop instalado

## Instalação
1. Clone o repositório
```bash
git clone <url-do-repo>
cd roteamento-docker
```
2. Subir os containers
```bash
docker compose build
docker compose up -d
```
3. Conferir se os 5 containers estão de pé
```bash
docker ps
```
## Como aplicar um protocolo
Os scripts aplicar.bat/aplicar.sh copiam o daemons e o frr.conf para dentro de cada roteador e reiniciam o FRR.

Windows (CMD):
```cmd
aplicar.bat rip
```
```cmd
aplicar.bat ospf
```
Mac / Linux:
```bash
chmod +x aplicar.sh
./aplicar.sh rip
./aplicar.sh ospf
```
**Obs: Trocar de protocolo é só rodar o script de novo com o outro parâmetro, pois ele sobrescreve a configuração anterior em todos os roteadores.**

Para aplicar o algoritmo proprio, o processo é diferente. Se executou os protocolos rip ou ospf anteriormente, então execute esses comandos antes de prosseguir.
```bash
docker exec R1 service frr stop
docker exec R2 service frr stop
docker exec R3 service frr stop
docker exec R4 service frr stop
docker exec R5 service frr stop
```
Garantindo o frr desligado em cada um dos containers, então somente copiar os arquivos algoritmo_proprio.py e main.py para dentro dos containers e executar a main.
```bash
docker cp algoritmo_proprio.py R1:/opt/
docker cp agente_link_state.py R2:/opt/
docker cp agente_link_state.py R3:/opt/
docker cp agente_link_state.py R4:/opt/
docker cp agente_link_state.py R5:/opt/
docker cp main.py R1:/opt/
docker cp main.py R2:/opt/
docker cp main.py R3:/opt/
docker cp main.py R4:/opt/
docker cp main.py R5:/opt/
docker exec -d R1 sh -c "python3 /opt/main.py > /var/log/agente.log 2>&1"
docker exec -d R2 sh -c "python3 /opt/main.py > /var/log/agente.log 2>&1"
docker exec -d R3 sh -c "python3 /opt/main.py > /var/log/agente.log 2>&1"
docker exec -d R4 sh -c "python3 /opt/main.py > /var/log/agente.log 2>&1"
docker exec -d R5 sh -c "python3 /opt/main.py > /var/log/agente.log 2>&1"
```
## Verificar o funcionamento
Ver a tabela de rotas de um roteador:
```bash
docker exec R1 vtysh -c "show ip route"
```
No caso do algoritmo proprio, executar:
```bash
docker exec R1 ip route
```
Testar conectividade entre roteadores (ex.: R1 até a interface de R4):
```bash
docker exec R1 ping -c 4 192.168.7.3
```
```bash
docker exec R1 traceroute 192.168.7.3
```
Entrar no shell interativo do FRR de um roteador (RIP e OSPF):
```bash
docker exec -it R1 vtysh
```
Aumentar a latência de uma interface do roteador:
```bash
docker exec R1 tc qdisc replace dev eth1 root netem delay 100ms
```
**Lembre-se de trocar R1 pelo roteador desejado; o mesmo caso se aplica para os IPs e as interfaces.**
## Comandos úteis
- `docker compose down` - Derruba todos os containers e redes
- `docker restart R1` - Reinicia um roteador
- `docker exec R1 service frr status` - Confere se os daemons do FRR estão rodando
- `docker exec R1 ps aux` - Lista os processos ativos dentro do roteador
- `docker exec R4 iperf3 -s` - Executa o servidor da ferramenta iperf3
