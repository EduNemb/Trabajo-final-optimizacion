# %%
import gurobipy as gp
from gurobipy import GRB

# 1. Conjuntos y parámetros

P = 17                      # número de ingenieros
D = 30                      # número de días del mes (mayo 2022)

I = range(1, P + 1)         # i = 1..17  (ingenieros)
J = range(1, D + 1)         # j = 1..30  (días del mes)

# Turnos: 1 = Diurno (solo FS), 2 = Nocturno, 3 = Madrugada
DIA, NOCHE, MADRUGADA = 1, 2, 3

# Mayo de 2022 inició en domingo -> fines de semana (sábado y domingo):
DIAS_FS = {1, 7, 8, 14, 15, 21, 22, 28, 29}


def turnos_disponibles(j):
    """Cj: conjunto de turnos disponibles el día j."""
    if j in DIAS_FS:
        return [DIA, NOCHE, MADRUGADA]
    else:
        return [NOCHE, MADRUGADA]


# 2. Modelo

modelo = gp.Model("Asignacion_Turnos_Ingenieros")
#Quitar salida de Gurobi en consola
modelo.Params.OutputFlag = 0


# Variables x[i,j,k], solo se crean para los k realmente disponibles el día j
x = {}
for j in J:
    for k in turnos_disponibles(j):
        for i in I:
            x[i, j, k] = modelo.addVar(vtype=GRB.BINARY, name=f"x_{i}_{j}_{k}")

# Z: cota superior de guardias por ingeniero (entera, por ser cota de suma de binarias)
Z = modelo.addVar(vtype=GRB.INTEGER, lb=0, name="Z")

modelo.update()


# 3. Función objetivo:  min Z

modelo.setObjective(Z, GRB.MINIMIZE)

# 4. Restricciones

# (2) Techo de carga: la carga total de cada ingeniero no supera Z
for i in I:
    carga_i = gp.quicksum(x[i, j, k] for j in J for k in turnos_disponibles(j))
    modelo.addConstr(carga_i <= Z, name=f"techo_carga_{i}")

# (3) Cobertura exacta: cada turno de cada día lo cubre exactamente un ingeniero
for j in J:
    for k in turnos_disponibles(j):
        modelo.addConstr(
            gp.quicksum(x[i, j, k] for i in I) == 1,
            name=f"cobertura_{j}_{k}"
        )

# (4) Máximo un turno por día por ingeniero
for i in I:
    for j in J:
        turnos_j = turnos_disponibles(j)
        modelo.addConstr(
            gp.quicksum(x[i, j, k] for k in turnos_j) <= 1,
            name=f"un_turno_dia_{i}_{j}"
        )

# (5) No dos fines de semana consecutivos (mismo turno k, ingeniero i)
#     j, j+1 = sábado/domingo de un FS ; j+7, j+8 = sábado/domingo del FS siguiente
for i in I:
    for j in J:
        if (j + 8) in J:  # asegura que j, j+1, j+7, j+8 existan dentro del mes
            for k in [DIA, NOCHE, MADRUGADA]:
                terms = []
                for jj in (j, j + 1, j + 7, j + 8):
                    if (i, jj, k) in x:
                        terms.append(x[i, jj, k])
                if terms:
                    modelo.addConstr(
                        gp.quicksum(terms) <= 1,
                        name=f"no_fs_consecutivos_{i}_{j}_{k}"
                    )

# (6) Descanso mínimo de 12h tras un turno de noche
#     (impide madrugada y día del día siguiente)
for i in I:
    for j in J:
        if (j + 1) in J:
            terms = []
            if (i, j, NOCHE) in x:
                terms.append(x[i, j, NOCHE])
            if (i, j + 1, MADRUGADA) in x:
                terms.append(x[i, j + 1, MADRUGADA])
            if (i, j + 1, DIA) in x:
                terms.append(x[i, j + 1, DIA])
            if len(terms) >= 2:  # solo aporta si hay al menos 2 términos reales
                modelo.addConstr(
                    gp.quicksum(terms) <= 1,
                    name=f"descanso_noche_{i}_{j}"
                )

# (7) Descanso mínimo de 12h tras un turno de día
#     (impide madrugada del día siguiente)
for i in I:
    for j in J:
        if (j + 1) in J:
            terms = []
            if (i, j, DIA) in x:
                terms.append(x[i, j, DIA])
            if (i, j + 1, MADRUGADA) in x:
                terms.append(x[i, j + 1, MADRUGADA])
            if len(terms) >= 2:
                modelo.addConstr(
                    gp.quicksum(terms) <= 1,
                    name=f"descanso_dia_{i}_{j}"
                )

# 5. Resolver


modelo.optimize()


# 6. Resultados

nombre_turno = {DIA: "Diurno", NOCHE: "Nocturno", MADRUGADA: "Madrugada"}

if modelo.status == GRB.OPTIMAL:
    print(f"\nCarga máxima óptima (Z*) = {Z.X:.0f} guardias por ingeniero\n")

    print("Cronograma de asignación (día - turno - ingeniero):")
    for j in J:
        for k in turnos_disponibles(j):
            asignado = None
            for i in I:
                if x[i, j, k].X > 0.5:
                    asignado = i
                    break
            print(f"  Día {j:2d} | {nombre_turno[k]:9s} -> Ingeniero {asignado}")

    print("\nCarga total por ingeniero:")
    for i in I:
        carga = sum(x[i, j, k].X for j in J for k in turnos_disponibles(j))
        print(f"  Ingeniero {i:2d}: {carga:.0f} guardias")
else:
    print(f"El modelo no encontró solución óptima. Status: {modelo.status}")


