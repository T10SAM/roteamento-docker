#!/usr/bin/env python3
"""
main.py

So' a "fiacao": cria os sockets, dispara as threads e liga tudo na
classe AgenteLinkState (definida em agente_link_state.py). Toda a
logica de roteamento fica no outro arquivo -- aqui e' so' orquestracao.
"""

import json
import os
import socket
import threading
import time

from algoritmo_proprio import AgenteLinkState, medir_latencia, INTERVALO

PORTA_HELLO = 5006
PORTA_LSA = 5007


def loop_hello_envio(agente, sock):
    while True:
        for i in agente.interfaces:
            msg = json.dumps({"nome": agente.nome, "ip": i["ip"]}).encode()
            try:
                sock.sendto(msg, (i["broadcast"], PORTA_HELLO))
            except OSError:
                pass
        time.sleep(INTERVALO / 2)


def loop_hello_recepcao(agente, sock):
    ips_locais = {i["ip"] for i in agente.interfaces}
    while True:
        dados, endereco = sock.recvfrom(65535)
        try:
            msg = json.loads(dados.decode())
        except json.JSONDecodeError:
            continue
        if endereco[0] in ips_locais:
            continue
        agente.registrar_hello(msg.get("nome", endereco[0]), endereco[0])


def loop_expira_vizinhos(agente):
    while True:
        time.sleep(INTERVALO)
        agente.expirar_vizinhos()


def loop_latencia(agente):
    while True:
        with agente.lock:
            ips = list(agente.vizinhos.keys())
        for ip in ips:
            agente.atualizar_latencia(ip, medir_latencia(ip))
        time.sleep(INTERVALO)


def loop_expira_lsdb(agente):
    while True:
        time.sleep(INTERVALO)
        agente.expirar_lsdb()


def loop_origina_periodico(agente):
    while True:
        time.sleep(INTERVALO)
        agente.originar_lsa()


def fazer_enviar_lsa(agente, sock_lsa):
    """Fecha sobre o socket de LSA e devolve a funcao que o agente usa para inundar."""
    def enviar(msg, ip_que_enviou):
        dados = json.dumps(msg).encode()
        with agente.lock:
            destinos = [ip for ip in agente.vizinhos if ip != ip_que_enviou]
        for ip in destinos:
            try:
                sock_lsa.sendto(dados, (ip, PORTA_LSA))
            except OSError:
                pass
    return enviar


def loop_lsa_recepcao(agente, sock):
    while True:
        dados, endereco = sock.recvfrom(65535)
        try:
            msg = json.loads(dados.decode())
        except json.JSONDecodeError:
            continue
        agente.processar_lsa_recebida(msg, endereco[0])


def main():
    nome = os.environ.get("ROUTER_NOME", socket.gethostname())
    agente = AgenteLinkState(nome)

    sock_hello = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_hello.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_hello.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock_hello.bind(("0.0.0.0", PORTA_HELLO))

    sock_lsa = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_lsa.bind(("0.0.0.0", PORTA_LSA))

    agente.enviar_lsa_callback = fazer_enviar_lsa(agente, sock_lsa)

    threading.Thread(target=loop_hello_envio, args=(agente, sock_hello), daemon=True).start()
    threading.Thread(target=loop_hello_recepcao, args=(agente, sock_hello), daemon=True).start()
    threading.Thread(target=loop_expira_vizinhos, args=(agente,), daemon=True).start()
    threading.Thread(target=loop_latencia, args=(agente,), daemon=True).start()
    threading.Thread(target=loop_lsa_recepcao, args=(agente, sock_lsa), daemon=True).start()
    threading.Thread(target=loop_expira_lsdb, args=(agente,), daemon=True).start()

    loop_origina_periodico(agente)  # loop principal, bloqueia aqui


if __name__ == "__main__":
    main()