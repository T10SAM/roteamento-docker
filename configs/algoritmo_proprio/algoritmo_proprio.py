#!/usr/bin/env python3

import heapq
import ipaddress
import json
import os
import subprocess
import time
from threading import Lock

PESO_SALTO = 10 
INTERVALO = 10 # Intervalo de tempo em que o agente mede a latencia
TIMEOUT_VIZINHO = 30 # Se nao chega HELLO de um vizinho por esse tempo, ele é considerado fora do ar
TIMEOUT_LSA = 60

NOME = os.environ.get("ROUTER_NOME", None)  # main.py resolve o fallback p/ hostname

# Pergunta ao proprio sistema operacional (ip addr) quais interfaces de rede este container tem e qual IP/sub-rede cada uma usa.
def obter_interfaces():
    saida = subprocess.run(["ip", "-4", "-j", "addr", "show"],
                            capture_output=True, text=True)
    dados = json.loads(saida.stdout)
    interfaces = []
    for item in dados:
        if item["ifname"] == "lo":
            continue # ignora a interface de loopback (127.0.0.1)
        for addr in item.get("addr_info", []):
             # Monta o objeto de rede a partir do IP e da mascara
            rede = ipaddress.ip_interface(f'{addr["local"]}/{addr["prefixlen"]}')
            interfaces.append({
                "iface": item["ifname"], "ip": addr["local"],
                "rede": str(rede.network), "broadcast": str(rede.network.broadcast_address),
            })
    return interfaces

# Mede a latencia (em milissegundos) ate um IP vizinho usando comando ping
def medir_latencia(ip, tentativas=3):
    try:
        saida = subprocess.run(
            ["ping", "-c", str(tentativas), "-W", "1", ip],
            capture_output=True, text=True, timeout=5
        )
        for linha in saida.stdout.splitlines():
            if "rtt" in linha or "round-trip" in linha:
                return float(linha.split("=")[1].strip().split("/")[1])
    except Exception:
        pass
    return None # Retorna None se o vizinho nao responder


def dijkstra(grafo, origem, roteadores):
    dist = {r: float('inf') for r in roteadores} # comeca com "custo infinito" para todos
    dist[origem] = 0
    primeiro_salto = {r: None for r in roteadores} 
    fila = [(0, origem)] # fila de prioridade (heap): sempre processa o nó mais barato primeiro

    while fila:
        custo_atual, u = heapq.heappop(fila)
        if custo_atual > dist[u]: # Se o caminho encontrado for pior, ignora esta entrada
            continue
        for v, custo_enlace, ip_proximo in grafo.get(u, []):
            novo_custo = custo_atual + custo_enlace
            if novo_custo < dist[v]:
                dist[v] = novo_custo
                primeiro_salto[v] = ip_proximo if u == origem else primeiro_salto[u]
                heapq.heappush(fila, (novo_custo, v))
    return dist, primeiro_salto

# Guarda o estado de um roteador: interfaces locais, vizinhos diretos, a LSDB (mapa da rede inteira) e a tabela de rotas calculada.
class AgenteLinkState:
    def __init__(self, nome):
        self.nome = nome
        self.interfaces = obter_interfaces()
        self.redes_diretas = {i["rede"] for i in self.interfaces}
        self.vizinhos = {} # tabela de vizinhança {"nome","iface","rede","ultimo_hello","latencia"}
        self.lsdb = {} #conhecimento de quem está ligado a quem {"seq","links","atualizado_em"}
        self.seq_local = 0
        self.tabela = {} # resultado final do Dijkstra {"custo","next_hop_ip"}
        self.lock = Lock()
        self.enviar_lsa_callback = None  # injetado pelo main.py: fn(msg, ip_excecao)
        print(f"[{self.nome}] Interfaces: {self.interfaces}")

    # Chamado toda vez que chega uma mensagem HELLO de outro roteador.
    def registrar_hello(self, nome_vizinho, ip_origem):
        iface_local, rede_local = self._iface_para_ip(ip_origem)
        if iface_local is None:
            return
        novo = ip_origem not in self.vizinhos
        with self.lock:
            self.vizinhos[ip_origem] = {
                "nome": nome_vizinho, "iface": iface_local, "rede": rede_local,
                "ultimo_hello": time.time(), # carimbo de tempo, usado por expirar_vizinhos()
                "latencia": self.vizinhos.get(ip_origem, {}).get("latencia"),
            }
        if novo:
            print(f"[{self.nome}] Novo vizinho: {nome_vizinho} ({ip_origem})")

    # Remove da lista de vizinhos quem nao manda HELLO
    def expirar_vizinhos(self):
        agora = time.time()
        mudou = False
        with self.lock:
            for ip in list(self.vizinhos.keys()):
                if agora - self.vizinhos[ip]["ultimo_hello"] > TIMEOUT_VIZINHO:
                    print(f"[{self.nome}] Vizinho {self.vizinhos[ip]['nome']} caiu")
                    del self.vizinhos[ip]
                    mudou = True
        if mudou:
            self.originar_lsa()

    # Descobre em qual das interfaces um IP vizinho se encaixa
    def _iface_para_ip(self, ip):
        for i in self.interfaces:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(i["rede"]):
                return i["iface"], i["rede"]
        return None, None

    def _ip_local_da_rede(self, rede):
        for i in self.interfaces:
            if i["rede"] == rede:
                return i["ip"]
        return None

    def atualizar_latencia(self, ip, latencia):
        mudou_muito = False
        with self.lock:
            if ip in self.vizinhos:
                antiga = self.vizinhos[ip]["latencia"]
                self.vizinhos[ip]["latencia"] = latencia
                if latencia is not None and (antiga is None or abs(latencia - antiga) > 2):
                    mudou_muito = True
        if mudou_muito:
            self.originar_lsa()

    # Monta e divulga a LSA, enviando uma mensagem contendo os links diretos e a latencia de cada um
    # Cada roteador que receber essa LSA monta seu proprio mapa
    def originar_lsa(self):
        with self.lock:
            self.seq_local += 1
            links = []
            for ip, v in self.vizinhos.items():
                if v["latencia"] is None:
                    continue
                links.append({
                    "vizinho": v["nome"], "rede": v["rede"],
                    "ip_local": self._ip_local_da_rede(v["rede"]),
                    "ip_vizinho": ip, "latencia": v["latencia"],
                })
            self.lsdb[self.nome] = {"seq": self.seq_local, "links": links,"atualizado_em": time.time()}
        msg = {"origem": self.nome, "seq": self.seq_local, "links": links}
        if self.enviar_lsa_callback:
            self.enviar_lsa_callback(msg, None)
        self.recalcular_rotas() # Caso a latência mude ou perca um vizinho, então deve recalcular as rotas

    # Chamado pelo main.py sempre que chega uma LSA de outro roteador
    # Se a LSA é mais nova do que a que tinha (seq maior), atualiza o mapa e repassa essa LSA para os outros vizinhos
    # Se for mais velha, então é ignorada
    def processar_lsa_recebida(self, msg, ip_de_quem_enviou):
        origem = msg["origem"]
        if origem == self.nome:
            return
        with self.lock:
            atual = self.lsdb.get(origem)
            eh_novidade = atual is None or msg["seq"] > atual["seq"]
            if eh_novidade:
                self.lsdb[origem] = {"seq": msg["seq"], "links": msg["links"],
                                      "atualizado_em": time.time()}
        if eh_novidade:
            if self.enviar_lsa_callback:
                self.enviar_lsa_callback(msg, ip_de_quem_enviou)  # propaga adiante
            self.recalcular_rotas()

    # Roda periodicamente removendo do mapa qualquer roteador cuja LSA nao foi renovada há mais de TIMEOUT_LSA segundos.
    def expirar_lsdb(self):
        agora = time.time()
        mudou = False
        with self.lock:
            for origem in list(self.lsdb.keys()):
                if origem == self.nome:
                    continue # nunca expira a propria entrada
                if agora - self.lsdb[origem]["atualizado_em"] > TIMEOUT_LSA:
                    print(f"[{self.nome}] LSA de {origem} expirou")
                    del self.lsdb[origem]
                    mudou = True
        if mudou:
            self.recalcular_rotas()

    # A partir de tudo que se sabe sobre a rede, remonta o grafo completo e roda Dijkstra
    def recalcular_rotas(self):
        with self.lock:
            lsdb_copia = dict(self.lsdb)

        # Monta a lista de todos os roteadores que aparecem em algum lugar do mapa
        roteadores = {self.nome} | set(lsdb_copia.keys())
        for info in lsdb_copia.values():
            for link in info["links"]:
                roteadores.add(link["vizinho"])

        # Monta o grafo no formato que a funcao dijkstra() espera: (vizinho, custo_do_link, ip_do_proximo_salto)
        grafo = {r: [] for r in roteadores}
        for origem, info in lsdb_copia.items():
            for link in info["links"]:
                custo = PESO_SALTO + link["latencia"]
                grafo[origem].append((link["vizinho"], custo, link["ip_vizinho"]))

        dist, primeiro_salto = dijkstra(grafo, self.nome, roteadores)

         # A partir das distancias calculadas, é decidido a rota para cada REDE
        nova_tabela = {}
        for origem, info in lsdb_copia.items():
            for link in info["links"]:
                rede = link["rede"]
                if rede in self.redes_diretas:
                    continue # Se for rede propria, diretamente conectada, então não precisa de rota
                custo_origem = dist.get(origem, float('inf'))
                if custo_origem == float('inf') or primeiro_salto[origem] is None:
                    continue
                # Se já temos uma rota mais barata para essa rede, mantemos a mais barata
                if rede not in nova_tabela or custo_origem < nova_tabela[rede]["custo"]:
                    nova_tabela[rede] = {"custo": custo_origem,
                                          "next_hop_ip": primeiro_salto[origem]}

        with self.lock:
            self.tabela = nova_tabela
        self._aplicar_rotas()
        self._imprimir_tabela()

    #Instala cada rota calculada na tabela de roteamento REAL do kernel Linux, usando o comando "ip route replace"
    def _aplicar_rotas(self):
        with self.lock:
            itens = list(self.tabela.items())
        for rede, info in itens:
            subprocess.run(["ip", "route", "replace", rede, "via", info["next_hop_ip"]],
                            capture_output=True)

    def _imprimir_tabela(self):
        with self.lock:
            print(f"\n=== {self.nome} | roteadores conhecidos: "
                  f"{list(self.lsdb.keys()) + [self.nome]} | {time.strftime('%H:%M:%S')} ===")
            for rede, info in sorted(self.tabela.items()):
                print(f"  {rede:<20} custo={info['custo']:<6.1f} via={info['next_hop_ip']}")
