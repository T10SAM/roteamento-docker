# algoritmo_proprio.py
 
rotas = [
{
"nome": "R1-R2-R5",
"saltos": 2,
"latencia": 15
},
{
"nome": "R1-R3-R4-R5",
"saltos": 3,
"latencia": 8
}
]
 
for rota in rotas:
rota["custo"] = (rota["saltos"] * 10) + rota["latencia"]
 
melhor = min(rotas, key=lambda r: r["custo"])
 
print("Resultados:")
for r in rotas:
print(
f"{r['nome']} -> "
f"Saltos={r['saltos']} "
f"Latência={r['latencia']}ms "
f"Custo={r['custo']}"
)
 
print(f"\nMelhor rota: {melhor['nome']}")
