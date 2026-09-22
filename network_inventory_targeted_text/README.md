# Network Inventory MVP — Ansible + Junos

MVP para detectar movimientos de usuarios que utilizan una computadora fija.

## Modelo

- `Everest Id` = identidad del usuario.
- `MAC Address` = identidad de la computadora fija.
- Ansible consulta en modo **read-only** la tabla MAC de los switches Juniper.
- El sistema compara la ubicación detectada contra el inventario base.

Estados iniciales:

- `SAME`
- `PORT_MOVED`
- `SWITCH_MOVED`
- `VLAN_CHANGED`
- combinaciones `...+VLAN_CHANGED`
- `NOT_FOUND`
- `AMBIGUOUS`

## 1. Requisitos del control node

Recomendado por la documentación actual de Juniper:

- Python 3.10+
- Ansible 2.17+
- Junos PyEZ 2.7.3+
- NETCONF habilitado en los switches
- usuario de consulta con los permisos apropiados

Instalación sugerida:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml
```

## 2. Configura switches

Edita:

```text
inventory/hosts.yml
```

Reemplaza las IP de ejemplo por las IP de gestión reales.

Las variables comunes están en:

```text
inventory/group_vars/all.yml
```

Esta versión usa NETCONF en TCP/830 y `juniper.device.junos`.

No guardes contraseñas productivas en texto plano. Para una primera prueba puedes pasar usuario por CLI y pedir la contraseña interactiva:

```bash
ansible-playbook playbooks/collect_mac_table.yml -u TU_USUARIO -k
```

Para producción, usar Ansible Vault.

## 3. Carga el inventario base

Archivo:

```text
baseline/inventory.csv
```

Cabeceras esperadas:

```text
Floor
Switch
Switch Port number
Desk Details
Client
Everest Id
Agent/Support/Empty
Port Status
WS Status
MAC Address
VLAN
IPv4 Address
```

El importador normaliza MACs con caracteres `\\` y elimina filas exactamente duplicadas para el seguimiento.

Solo se rastrean en esta primera versión las filas que tienen al mismo tiempo:

```text
Everest Id + MAC Address
```

## 4. Define uplinks/trunks

Edita:

```text
baseline/uplinks.csv
```

Ejemplo:

```csv
Switch,Interface
FSMEXICOASW01,ge-0/0/47
FSMEXICOASW01,ge-0/0/48
FSMEXICOASW08,ae0
```

Esos puertos quedan excluidos como ubicación final de una PC.

## 5. Primera recolección

```bash
ansible-playbook playbooks/collect_mac_table.yml -u TU_USUARIO -k
```

Ansible ejecuta únicamente:

```text
show ethernet-switching table
```

usando `juniper.device.junos_command` con salida XML estructurada.

Los resultados por switch se guardan en:

```text
data/raw/FSMEXICOASW01.json
data/raw/FSMEXICOASW02.json
...
```

## 6. Comparar contra baseline

```bash
python3 scripts/compare_inventory.py
```

Resultado:

```text
data/output/current_inventory.csv
```

También se crea:

```text
data/output/source_duplicates.csv
```

para revisar duplicados encontrados en el archivo original.

## 7. Ejecutar todo

```bash
./run_scan.sh -u TU_USUARIO -k
```

## Ejemplo de resultado

```csv
everest_id,mac,status,baseline_switch,baseline_interface,current_switch,current_interface
sf752038,d0:46:0c:97:6b:dd,SWITCH_MOVED,NY4823305571(ASW01),ge-0/0/0,FSMEXICOASW08,ge-0/0/24
```

## Importante para la primera prueba

La estructura XML devuelta por `show ethernet-switching table` puede variar ligeramente según familia/modelo y release de Junos. El parser del MVP busca recursivamente MAC, interfaz y VLAN, pero la primera captura real de uno de tus switches será la que usaremos para afinarlo al 100%.

No hay tareas `set`, `delete`, `commit` ni módulos de configuración en este MVP.

## Siguiente etapa propuesta

Después de validar la recolección real:

1. Afinar parser con la estructura exacta de tus EX.
2. Crear catálogo `switch + interface -> Desk Details`.
3. Guardar snapshots e historial de movimientos.
4. Añadir IP mediante ARP/DHCP.
5. Programar polling con AWX/Automation Controller o scheduler.
6. Añadir dashboard y alertas.

---

## Ansible Tower / Automation Controller

If this project is executed from Ansible Tower, use:

```text
playbooks/tower_scan.yml
```

and follow:

```text
tower/SETUP.md
```

The Tower version uses the Tower Inventory and Credential instead of `inventory/hosts.yml`, keeps per-job temporary files under `/tmp`, prints detected events in the Job Output, and publishes summary/event data with `set_stats`.


## AWX compatibility note (no jxmlease required)

This build collects `show ethernet-switching table` with `display: text` so the playbook does not require the Python package `jxmlease` merely to parse XML output. The comparator already includes a text-output fallback parser. If your Execution Environment later includes `jxmlease`, XML collection can be re-enabled for richer structured parsing.
