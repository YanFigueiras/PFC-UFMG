# PFC-UFMG — Exploração Multi-Robô com Manutenção de Conectividade (DRBECM)

Projeto de Fim de Curso (PFC) desenvolvido no **Laboratório CORO da UFMG**, sob
orientação do **Prof. Luciano Cunha de Araújo Pimenta**. Este repositório contém
o código-fonte, o ambiente de simulação e os scripts experimentais que servem de
base para a monografia.

> Na exploração de ambientes desconhecidos por equipes de drones há um
> compromisso fundamental: avançar rápido em direção a regiões inexploradas tende
> a romper a comunicação com a base, enquanto manter a equipe coesa limita a
> velocidade de exploração. Este trabalho **adapta, implementa, avalia em
> simulação e valida experimentalmente** o algoritmo *Dynamic Role-Based
> Exploration with Connectivity Maintenance* (**DRBECM**), proposto por
> Chaabi e Mitton (2025), que organiza a equipe em dois papéis dinâmicos
> — **exploradores** e **agentes de suporte** — alternados de forma distribuída
> para equilibrar a expansão da fronteira e a manutenção de uma cadeia de
> comunicação multi-salto até a base.

A adaptação incorpora restrições físicas dos quadrirrotores **Crazyflie 2.1**
(limites de velocidade e aceleração, distância mínima entre agentes, margem de
conectividade, sequência de decolagem e pouso e reparo iterativo de alvos),
executando sobre **ROS 2 Humble** e o simulador **CrazySim / Gazebo Garden**.

## Demonstrações em vídeo

Ambos os vídeos foram gerados com **o mesmo conjunto de parâmetros**:

- 🎥 **Experimento físico** (arena do CORO): https://youtu.be/Sxqze_U8zEM
- 🎥 **Ensaio simulado** (Gazebo): https://youtu.be/kkQvVk_WbOk

## Estrutura do repositório

```
.
├── docker-compose.yaml          # Orquestra o container de simulação (crazysim)
├── docker/
│   ├── sim.Dockerfile           # Imagem ROS 2 Humble + Gazebo Garden + CrazySim
│   └── vg.Dockerfile
└── shared/                      # Volumes montados no container (/CrazySim)
    ├── pfc_ws/                  # >>> Trabalho original deste PFC <<<
    │   ├── src/
    │   │   ├── drbecm_coro/             # Controlador de exploração DRBECM
    │   │   ├── control_validation/      # Validação de controle (simulação)
    │   │   └── control_validation_coro/ # Validação de controle (cenário CORO)
    │   └── worlds/              # Mundos Gazebo (coro.world, porcelain_room.world)
    ├── startup/                 # Scripts tmuxinator de inicialização
    ├── crazyflie-firmware/      # Dependência: firmware Crazyflie (SITL)
    ├── crazyflie-lib-python/    # Dependência: cflib
    └── crazyswarm2_ws/          # Dependência: workspace Crazyswarm2
```

> **Nota:** os diretórios `crazyflie-firmware`, `crazyflie-lib-python` e
> `crazyswarm2_ws` são dependências de terceiros (clonadas automaticamente pelo
> `docker/sim.Dockerfile` a partir do projeto [CrazySim](https://github.com/gtfactslab/CrazySim)).
> Estão versionadas aqui para reproduzir exatamente o ambiente usado nos
> experimentos.

## Pacote principal: `drbecm_coro`

Adaptação ROS 2 do algoritmo DRBECM. A lógica é separada em:

- `algorithm.py` — núcleo do DRBECM (papéis dinâmicos, fronteiras, conectividade);
- `node.py` — adaptador ROS 2 (poses, publicação de comandos Crazyflie, fases de
  voo: `WAIT_FOR_POSES` → decolagem → exploração → pouso);
- `metrics.py` — coleta de métricas (cobertura, conectividade);
- `visualization.py` — markers e mapa de ocupação para RViz.

Parâmetros de controle (definidos em `node.py`): altura de voo `1.00 m`,
planejamento a `5 Hz`, controle a `20 Hz`, `MAX_SPEED = 0.15 m/s`,
`MAX_ACCELERATION = 0.05 m/s²`, decolagem/pouso automáticos.

## Pré-requisitos

- Docker e Docker Compose
- GPU NVIDIA com `nvidia-container-toolkit` (o compose usa `runtime: nvidia`)
- Servidor X11 no host (para a GUI do Gazebo/RViz)

## Como executar

### 1. Construir e subir o container

```bash
# Permitir acesso ao display X11 (host)
xhost +local:root

# Construir a imagem e iniciar o container de simulação
docker compose up -d --build
```

### 2. Abrir um shell no container

```bash
docker exec -it crazysim bash
```

### 3. Iniciar a simulação DRBECM

Os scripts em `shared/startup/` montam sessões tmuxinator que compilam o
workspace e lançam SITL/Gazebo, o backend Crazyswarm2 e o nó DRBECM:

```bash
# Dentro do container:
/CrazySim/startup/start.sh                       # Simulação DRBECM completa
/CrazySim/startup/start_control_validation.sh    # Validação de controle (sim)
/CrazySim/startup/start_drbecm_real.sh           # DRBECM em drones reais
/CrazySim/startup/start_control_validation_real.sh
```

A sessão padrão (`session.yaml`) sobe três janelas:
`sitl_gazebo` (4 Crazyflies) → `crazyswarm2` (backend cflib) →
`drbecm` (`ros2 launch drbecm_coro drbecm.launch.py`).

## Referência

- M. Chaabi e N. Mitton (2025). *Dynamic Role-Based Exploration with
  Connectivity Maintenance* (DRBECM) — algoritmo base adaptado neste trabalho.

## Créditos

- **Autor:** Yan Figueiras
- **Orientador:** Prof. Luciano Cunha de Araújo Pimenta
- **Instituição:** Laboratório CORO — Universidade Federal de Minas Gerais (UFMG)
