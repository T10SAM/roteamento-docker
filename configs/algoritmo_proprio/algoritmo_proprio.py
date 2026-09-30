#!/usr/bin/env python3
"""
Algoritmo Proprio de Roteamento
Metrica hibrida: custo = (saltos x 10) + latencia

Para cada enlace e atribuida uma latencia em ms.
O custo de um enlace e: 10 + latencia_do_enlace
Ao acumular ao longo de um caminho:
  custo_total = sum(10 + lat_i) = (n_saltos x 10) + latencia_total

O algoritmo de Dijkstra encontra o menor custo para cada par de roteadores
e gera rotas estaticas no FRR.
"""

import heapq
import os

# Topologia: (roteador_a, roteador_b, latencia_ms, rede, ip_a, ip_b)
# As latencias foram escolhidas para que o algoritmo proprio produza
# caminhos diferentes dos do RIP (apenas saltos) e do OSPF (custo fixo).
ENLACES = [
    ('R1', 'R2', 10, '192.168.5.0/29', '192.168.5.2', '192.168.5.3'),
    ('R2', 'R3',  8, '192.168.6.0/29', '192.168.6.2', '192.168.6.3'),
    ('R3', 'R4',  2, '192.168.7.0/29', '192.168.7.2', '192.168.7.3'),
    ('R4', 'R5',  2, '192.168.8.0/29', '192.168.8.2', '192.168.8.3'),
    ('R5', 'R1',  9, '192.168.9.0/29', '192.168.9.3', '192.168.9.2'),
    ('R1', 'R3',  3, '192.100.1.0/29', '192.100.1.2', '192.100.1.3'),
    ('R5', 'R2',  3, '192.100.2.0/29', '192.100.2.2', '192.100.2.3'),
]

ROTEADORES = ['R1', 'R2', 'R3', 'R4', 'R5']


def construir_grafo():
    grafo = {r: [] for r in ROTEADORES}
    for ra, rb, lat, rede, ipa, ipb in ENLACES:
        custo = 10 + lat
        grafo[ra].append((rb, custo, ipb))
        grafo[rb].append((ra, custo, ipa))
    return grafo


def dijkstra(grafo, origem):
    dist = {r: float('inf') for r in ROTEADORES}
    dist[origem] = 0
    primeiro_salto = {r: None for r in ROTEADORES}
    fila = [(0, origem)]

    while fila:
        custo_atual, u = heapq.heappop(fila)
        if custo_atual > dist[u]:
            continue
        for v, custo_enlace, ip_proximo in grafo[u]:
            novo_custo = custo_atual + custo_enlace
            if novo_custo < dist[v]:
                dist[v] = novo_custo
                primeiro_salto[v] = ip_proximo if u == origem else primeiro_salto[u]
                heapq.heappush(fila, (novo_custo, v))

    return dist, primeiro_salto


def redes_conectadas(roteador):
    conectadas = set()
    for ra, rb, _, rede, _, _ in ENLACES:
        if ra == roteador or rb == roteador:
            conectadas.add(rede)
    return conectadas


def calcular_rotas():
    grafo = construir_grafo()
    rotas_por_roteador = {}

    for origem in ROTEADORES:
        dist, primeiro_salto = dijkstra(grafo, origem)
        conectadas = redes_conectadas(origem)
        rotas = {}

        for ra, rb, _, rede, _, _ in ENLACES:
            if rede in conectadas:
                continue
            custo_via_ra = dist[ra]
            custo_via_rb = dist[rb]

            if custo_via_ra <= custo_via_rb:
                proximo_hop = primeiro_salto[ra]
            else:
                proximo_hop = primeiro_salto[rb]

            melhor_custo = min(custo_via_ra, custo_via_rb)

            if rede not in rotas or melhor_custo < rotas[rede][0]:
                rotas[rede] = (melhor_custo, proximo_hop)

        rotas_por_roteador[origem] = [(rede, nh) for rede, (_, nh) in sorted(rotas.items())]

    return rotas_por_roteador


DAEMONS_TEMPLATE = """\
# This file tells the frr package which daemons to start.
#
# Sample configurations for these daemons can be found in
# /usr/share/doc/frr/examples/.
#
# ATTENTION:
#
# When activating a daemon for the first time, a config file, even if it is
# empty, has to be present *and* be owned by the user and group "frr", else
# the daemon will not be started by /etc/init.d/frr. The permissions should
# be u=rw,g=r,o=.
# When using "vtysh" such a config file is also needed. It should be owned by
# group "frrvty" and set to ug=rw,o= though. Check /etc/pam.d/frr, too.
#
# The watchfrr, zebra and staticd daemons are always started.
#
bgpd=no
ospfd=no
ospf6d=no
ripd=no
ripngd=no
isisd=no
pimd=no
pim6d=no
ldpd=no
nhrpd=no
eigrpd=no
babeld=no
sharpd=no
pbrd=no
bfdd=no
fabricd=no
vrrpd=no
pathd=no

#
# If this option is set the /etc/init.d/frr script automatically loads
# the config via "vtysh -b" when the servers are started.
# Check /etc/pam.d/frr if you intend to use "vtysh"!
#
vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
ospfd_options="  -A 127.0.0.1"
ospf6d_options=" -A ::1"
ripd_options="   -A 127.0.0.1"
ripngd_options=" -A ::1"
isisd_options="  -A 127.0.0.1"
pimd_options="   -A 127.0.0.1"
pim6d_options="  -A ::1"
ldpd_options="   -A 127.0.0.1"
nhrpd_options="  -A 127.0.0.1"
eigrpd_options=" -A 127.0.0.1"
babeld_options=" -A 127.0.0.1"
sharpd_options=" -A 127.0.0.1"
pbrd_options="   -A 127.0.0.1"
staticd_options="-A 127.0.0.1"
bfdd_options="   -A 127.0.0.1"
fabricd_options="-A 127.0.0.1"
vrrpd_options="  -A 127.0.0.1"
pathd_options="  -A 127.0.0.1"
"""


def gerar_configs(rotas_por_roteador, diretorio_saida):
    for roteador, rotas in rotas_por_roteador.items():
        pasta = os.path.join(diretorio_saida, roteador)
        os.makedirs(pasta, exist_ok=True)

        with open(os.path.join(pasta, 'daemons'), 'w') as f:
            f.write(DAEMONS_TEMPLATE)

        linhas = [
            "frr version 8.4.4",
            "frr defaults traditional",
            f"hostname {roteador}",
            "domainname localdomain",
            "log syslog informational",
            "no ipv6 forwarding",
            "service integrated-vtysh-config",
            "!",
        ]
        for rede, proximo_hop in rotas:
            linhas.append(f"ip route {rede} {proximo_hop}")
        linhas += ["!", "end", ""]

        with open(os.path.join(pasta, 'frr.conf'), 'w') as f:
            f.write("\n".join(linhas))


def imprimir_resumo(rotas_por_roteador):
    print("=== Algoritmo Proprio: Metrica Hibrida ===")
    print("Custo por enlace = 10 + latencia_ms")
    print()

    print("Latencias configuradas:")
    for ra, rb, lat, rede, _, _ in ENLACES:
        custo = 10 + lat
        print(f"  {ra}-{rb} ({rede}): lat={lat}ms -> custo={custo}")
    print()

    print("Tabela de rotas estaticas geradas:")
    for roteador in ROTEADORES:
        print(f"\n  {roteador}:")
        for rede, nh in rotas_por_roteador[roteador]:
            print(f"    {rede} via {nh}")


if __name__ == '__main__':
    rotas = calcular_rotas()
    imprimir_resumo(rotas)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    gerar_configs(rotas, base_dir)

    print("\nArquivos gerados em configs/algoritmo_proprio/R*/")
