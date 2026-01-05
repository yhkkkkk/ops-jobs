# Kubernetes GPU 调度完整指南

## 概述

Kubernetes 提供了多种方式来调度和管理 GPU 资源，从基础的设备插件到高级的资源共享机制。本指南涵盖了所有主要的 GPU 调度方法，包括详细的配置示例和最佳实践。

## 目录

1. [基础 GPU 调度](#基础-gpu-调度)
2. [NVIDIA GPU Operator](#nvidia-gpu-operator)
3. [Run:AI (NVIDIA AI 工作负载编排平台)](#runai-nvidia-ai-工作负载编排平台)
4. [HAMi (异构计算中间件)](#hami-异构计算中间件)
5. [KubeRay (Ray 分布式计算)](#kuberay-ray-分布式计算)
6. [Volcano (通用批处理调度器)](#volcano-通用批处理调度器)
7. [云服务商 GPU 调度](#云服务商-gpu-调度)
8. [AMD GPU Operator](#amd-gpu-operator)
9. [Intel GPU 调度](#intel-gpu-调度)
10. [GPU 时间切片 (Time Slicing)](#gpu-时间切片-time-slicing)
11. [MIG (Multi-Instance GPU)](#mig-multi-instance-gpu)
12. [MGS (Multi-Granularity GPU Scheduling)](#mgs-multi-granularity-gpu-scheduling)
13. [GPU 加速基础概念](#gpu-加速基础概念)
14. [GPU 通信与网络](#gpu-通信与网络)
15. [高级调度策略](#高级调度策略)
16. [实际使用案例](#实际使用案例)
17. [监控和故障排除](#监控和故障排除)
18. [最佳实践](#最佳实践)

## 基础 GPU 调度

### Device Plugin 方式

Kubernetes 通过设备插件框架来支持 GPU 调度。主要厂商包括 NVIDIA、AMD、Intel 等。

#### NVIDIA GPU 调度示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod-basic
spec:
  restartPolicy: OnFailure
  containers:
  - name: cuda-container
    image: nvidia/cuda:11.2-base-ubuntu20.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1  # 请求 1 个 GPU
  nodeSelector:
    accelerator: nvidia-tesla-k80  # 可选：指定 GPU 类型
```

#### AMD GPU 调度示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: amd-gpu-pod
spec:
  containers:
  - name: amd-container
    image: rocm/tensorflow:latest
    resources:
      limits:
        amd.com/gpu: 1
```

### Extended Resource 方式

对于不支持设备插件的 GPU，可以使用扩展资源。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: extended-gpu-pod
spec:
  containers:
  - name: gpu-app
    image: my-gpu-app:latest
    resources:
      limits:
        example.com/gpu: 1
```

## NVIDIA GPU Operator

NVIDIA GPU Operator 自动化管理 Kubernetes 中所有 NVIDIA GPU 软件组件。

### 安装 GPU Operator

```bash
# 使用 Helm 安装
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --version v25.10.1
```

### 验证安装

```bash
# 检查 GPU Operator 组件状态
kubectl get pods -n gpu-operator

# 检查节点 GPU 资源
kubectl describe node | grep -A 5 "nvidia.com/gpu"
```

### ClusterPolicy 配置

```yaml
apiVersion: nvidia.com/v1
kind: ClusterPolicy
metadata:
  name: cluster-policy
spec:
  dcgm:
    enabled: true
  dcgmExporter:
    config:
      name: ""
  devicePlugin:
    config:
      name: ""
  driver:
    enabled: true
  gfd:
    enabled: true
  migManager:
    enabled: false
  nodeStatusExporter:
    enabled: true
  operator:
    defaultRuntime: crio
    runtimeClass: nvidia
  psp:
    enabled: false
  sandboxDevicePlugin:
    enabled: false
  sandboxWorkloads:
    enabled: false
  toolkit:
    enabled: true
  validator:
    plugin:
      env:
      - name: WITH_WORKLOAD
        value: "true"
```

## HAMi (异构计算中间件)

HAMi (Heterogeneous AI computing Middleware) 是华为开源的异构计算中间件，支持多种 AI 芯片的统一管理和调度。HAMi 通常与 Volcano 调度器结合使用，提供更强大的 GPU 资源调度能力。

### HAMi 核心特性

- **多芯片支持**: 支持 NVIDIA GPU、AMD GPU、昇腾 NPU、寒武纪 MLU 等
- **细粒度调度**: 支持 GPU 内存、核心的精确分配
- **拓扑感知**: 考虑 GPU 间互联拓扑进行智能调度
- **Volcano 集成**: 与 Volcano 调度器深度集成

### 安装 HAMi

#### 方式一：Helm 安装

```bash
# 添加 HAMi Helm 仓库
helm repo add hami https://project-hami.github.io/HAMi/
helm repo update

# 安装 HAMi
helm install hami hami/hami --namespace kube-system
```

#### 方式二：YAML 安装

```bash
# 克隆 HAMi 仓库
git clone https://github.com/Project-HAMi/HAMi.git
cd HAMi

# 安装 HAMi 组件
kubectl apply -f manifests/
```

### HAMi + Volcano 集成

HAMi 通常与 Volcano 调度器结合使用，以提供更好的 GPU 调度能力。

#### 安装 Volcano

```bash
# 添加 Volcano Helm 仓库
helm repo add volcano-sh https://volcano-sh.github.io/helm-charts
helm repo update

# 安装 Volcano
helm install volcano volcano-sh/volcano \
  --namespace volcano-system \
  --create-namespace
```

#### 配置 Volcano 支持 vGPU

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: volcano-scheduler-configmap
  namespace: volcano-system
data:
  volcano-scheduler.conf: |
    actions: "enqueue, allocate, backfill"
    tiers:
    - plugins:
      - name: priority
      - name: gang
      - name: conformance
    - plugins:
      - name: drf
      - name: deviceshare
        arguments:
          deviceshare.VGPUEnable: true  # 启用 vGPU 支持
      - name: predicates
      - name: proportion
      - name: nodeorder
      - name: binpack
```

#### 部署 Volcano vGPU Device Plugin

```bash
# 部署 Volcano vGPU 设备插件
kubectl create -f https://raw.githubusercontent.com/Project-HAMi/volcano-vgpu-device-plugin/main/volcano-vgpu-device-plugin.yml
```

### HAMi 调度策略

#### 节点级调度策略

- **best-fit**: 优先选择内存剩余最少的 GPU（内存紧凑分配）
- **idle-first**: 优先选择空闲 GPU
- **numa-first**: 优先选择同一 NUMA 节点的 GPU

#### GPU 级调度策略

- **binpack**: 将所有 GPU 资源分配到同一张 GPU 卡
- **spread**: 将 GPU 资源分散到不同的 GPU 卡

### 使用 HAMi 调度 GPU

#### 基本 GPU 请求

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hami-gpu-pod
spec:
  containers:
  - name: gpu-container
    image: nvidia/cuda:11.2-base-ubuntu20.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1  # 请求 1 个物理 GPU
```

#### vGPU 请求 (与 Volcano 结合)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hami-vgpu-pod
spec:
  containers:
  - name: vgpu-container
    image: nvidia/cuda:11.2-base-ubuntu20.04
    command: ["sleep", "100000"]
    resources:
      limits:
        volcano.sh/vgpu-number: 2   # 请求 2 张 vGPU 卡
        volcano.sh/vgpu-memory: 3000  # 每张 vGPU 3GB 内存 (可选)
        volcano.sh/vgpu-cores: 50      # 每张 vGPU 50% 核心 (可选)
```

#### 调度策略配置

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hami-scheduled-pod
  annotations:
    nvidia.com/schedule-policy: "best-fit"  # 节点级调度策略
    hami.io/gpu-scheduler-policy: "spread"  # GPU级调度策略
spec:
  containers:
  - name: gpu-container
    image: ubuntu:18.04
    command: ["bash", "-c", "sleep 86400"]
    resources:
      limits:
        nvidia.com/gpu: 2  # 请求 2 个物理 GPU
```

#### 拓扑感知调度

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hami-topology-pod
  annotations:
    hami.io/node-scheduler-policy: "spread"  # 拓扑感知调度
spec:
  containers:
  - name: gpu-container
    image: cr.metax-tech.com/public-ai-release/c500/colossalai:2.24.0.5-py38-ubuntu20.04-amd64
    command: ["sleep", "infinity"]
    resources:
      limits:
        metax-tech.com/gpu: 1  # MetaX GPU
```

### HAMi 支持的设备类型

| 设备类型 | 资源名称 | 说明 |
|---------|---------|------|
| NVIDIA GPU | `nvidia.com/gpu` | NVIDIA GPU 物理卡 |
| AMD GPU | `amd.com/gpu` | AMD GPU 物理卡 |
| 昇腾 NPU | `hisi.com/Ascend910` | 华为昇腾 910 |
| 寒武纪 MLU | `cambricon.com/MLU` | 寒武纪 MLU |
| MetaX GPU | `metax-tech.com/gpu` | 燧原 MetaX GPU |

### 监控 HAMi

```bash
# 查看 HAMi 组件状态
kubectl get pods -n kube-system -l app.kubernetes.io/name=hami

# 查看 Volcano 调度器状态
kubectl get pods -n volcano-system

# 查看 GPU 资源分配
kubectl describe nodes | grep -A 5 "nvidia.com/gpu"
```

### HAMi 配置参数

```yaml
apiVersion: config.hami.io/v1alpha1
kind: HamiConfig
metadata:
  name: hami-config
spec:
  # 设备插件配置
  devicePlugin:
    enable: true
    deviceMemoryScaling: 1.0  # 设备内存缩放因子

  # 调度器配置
  scheduler:
    enable: true
    defaultSchedulePolicy: "best-fit"

  # 监控配置
  monitor:
    enable: true
    interval: "30s"
```

## GPU 调度方案对比

| 调度方案 | 隔离级别 | 集成复杂度 | 适用场景 | 开源状态 |
|---------|---------|-----------|---------|---------|
| **NVIDIA GPU Operator** | 硬件/软件 | 中等 | NVIDIA 生态 | ✅ 开源 |
| **HAMi + Volcano** | 软件隔离 | 复杂 | 多芯片异构 | ✅ 开源 |
| **AMD GPU Operator** | 软件隔离 | 中等 | AMD GPU | ✅ 开源 |
| **Intel GPU Plugin** | 软件隔离 | 简单 | Intel GPU | ✅ 开源 |
| **AWS EKS GPU** | 云原生 | 简单 | AWS 环境 | ☁️ 云服务 |
| **GCP GKE GPU** | 云原生 | 简单 | GCP 环境 | ☁️ 云服务 |
| **Azure AKS GPU** | 云原生 | 简单 | Azure 环境 | ☁️ 云服务 |
| **Time Slicing** | 软件共享 | 简单 | 资源共享 | ✅ 开源 |
| **MIG** | 硬件隔离 | 中等 | 推理服务 | ✅ NVIDIA |
| **MGS** | 概念框架 | 高 | 研究场景 | ❌ 非开源 |

## Run:AI (NVIDIA AI 工作负载编排平台)

### 什么是 Run:AI？

**Run:AI** 是 NVIDIA 推出的企业级 AI 工作负载编排和 GPU 管理平台，专门为 AI/ML 工作负载优化。提供动态资源分配、智能调度和完整的 AI 生命周期支持。

**核心特性**：
- **动态编排**: 自动分配和管理 GPU 资源
- **AI 生命周期管理**: 从开发到部署的全流程支持
- **多云集成**: 支持 AWS、GCP、Azure 等云平台
- **企业级治理**: 配额管理、成本控制、安全策略

### Run:AI 架构组件

#### 1. **控制平面 (Control Plane)**
```yaml
# Run:AI Operator 安装
apiVersion: helm.cilium.io/v1alpha1
kind: HelmRelease
metadata:
  name: runai-operator
  namespace: runai
spec:
  chart:
    name: runai-cluster
    version: "2.16.0"
  values:
    global:
      domain: runai.apps.cluster.example.com
    runai-operator:
      enabled: true
    runai-scheduler:
      enabled: true
```

#### 2. **调度器 (Scheduler)**
- **KAI Scheduler**: 开源 Kubernetes AI 调度器
- **GPU 感知调度**: 基于 GPU 拓扑和可用性进行智能调度
- **工作负载优先级**: 支持作业优先级和抢占

#### 3. **工作负载管理器 (Workload Manager)**
```yaml
# Run:AI 训练作业示例
apiVersion: run.ai/v1
kind: TrainingWorkload
metadata:
  name: bert-training
  namespace: runai
spec:
  gpu: 4
  cpu: 8
  memory: "32Gi"
  image: "nvcr.io/nvidia/pytorch:23.06-py3"
  command: ["python", "train.py"]
  workingDir: "/workspace"
  environment:
  - name: CUDA_VISIBLE_DEVICES
    value: "0,1,2,3"
  - name: NCCL_IB_DISABLE
    value: "0"
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

### Run:AI 与 Amazon EKS 集成

#### 集成方式
**Run:AI 作为 EKS 插件部署**：
1. **通过 AWS Marketplace 订阅**
2. **Helm Chart 安装到 EKS 集群**
3. **与 EKS GPU 节点组集成**

#### EKS 上的 Run:AI 配置

**1. EKS 集群准备**
```bash
# 创建 GPU 节点组
eksctl create nodegroup \
  --cluster my-cluster \
  --name gpu-nodes \
  --node-type p3.8xlarge \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4 \
  --node-volume-size 100 \
  --ssh-public-key my-key
```

**2. 安装 NVIDIA GPU Operator**
```bash
# 添加 NVIDIA Helm 仓库
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# 安装 GPU Operator
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --set driver.enabled=false  # EKS 已安装 NVIDIA 驱动
```

**3. 安装 Run:AI**
```bash
# 添加 Run:AI Helm 仓库
helm repo add runai https://runai-charts.storage.googleapis.com
helm repo update

# 安装 Run:AI 集群组件
helm install runai-cluster runai/runai-cluster \
  --namespace runai \
  --create-namespace \
  --set global.domain=runai.apps.cluster.example.com \
  --set runai-operator.enabled=true \
  --set runai-scheduler.enabled=true
```

#### 工作负载提交示例

**训练作业**:
```yaml
apiVersion: run.ai/v1
kind: TrainingWorkload
metadata:
  name: distributed-training
  namespace: runai
spec:
  gpu: 8  # 请求 8 个 GPU
  cpu: 16
  memory: "64Gi"
  image: "nvcr.io/nvidia/pytorch:23.06-py3"
  command: ["torchrun", "--nproc_per_node=8", "train.py"]
  workingDir: "/workspace"
  environment:
  - name: MASTER_ADDR
    value: "localhost"
  - name: MASTER_PORT
    value: "12355"
  - name: NCCL_SOCKET_IFNAME
    value: "eth0"
  nodeSelector:
    accelerator: nvidia-tesla-v100
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

**推理服务**:
```yaml
apiVersion: run.ai/v1
kind: InferenceWorkload
metadata:
  name: bert-inference
  namespace: runai
spec:
  gpu: 2
  cpu: 4
  memory: "16Gi"
  image: "nvcr.io/nvidia/tritonserver:23.06-py3"
  modelRepositoryPath: "/models"
  ports:
  - containerPort: 8000
    name: http
  - containerPort: 8001
    name: grpc
  nodeSelector:
    accelerator: nvidia-tesla-t4
```

### Run:AI 调度策略

#### 1. **GPU 共享与隔离**
- **时间分片 (Time Slicing)**: 多个工作负载共享 GPU
- **MIG 支持**: Multi-Instance GPU 分割
- **GPU 内存管理**: 精细化内存分配

#### 2. **智能调度算法**
- **拓扑感知调度**: 考虑 GPU 间互联拓扑
- **负载均衡**: 在集群 GPU 间均匀分布工作负载
- **抢占式调度**: 高优先级作业可抢占低优先级资源

#### 3. **资源配额管理**
```yaml
apiVersion: run.ai/v1
kind: RunaiProject
metadata:
  name: ml-team
  namespace: runai
spec:
  gpu: 16  # 项目 GPU 配额
  cpu: 64
  memory: "256Gi"
  users:
  - name: alice
    gpuQuota: 8
  - name: bob
    gpuQuota: 4
  nodePools:  # 指定节点池
  - name: gpu-pool-a100
    gpuType: "A100"
  - name: gpu-pool-v100
    gpuType: "V100"
```

### Run:AI 监控与观测

#### 1. **Run:AI Dashboard**
- 实时 GPU 利用率监控
- 工作负载状态跟踪
- 资源使用分析

#### 2. **Prometheus 集成**
```yaml
# Run:AI 指标暴露
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: runai-monitor
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: runai
  endpoints:
  - port: metrics
    interval: 30s
```

#### 3. **日志与事件**
- 详细的工作负载执行日志
- GPU 分配和释放事件
- 调度决策审计

### Run:AI vs 其他 GPU 调度方案

| 特性 | Run:AI | NVIDIA GPU Operator | KubeRay | Volcano |
|-----|--------|-------------------|---------|---------|
| **专注领域** | AI/ML 工作负载 | GPU 设备管理 | Ray 分布式计算 | 通用批处理调度 |
| **调度智能** | AI 优化算法 | 基础调度 | Ray 特定 | 通用调度 |
| **生命周期管理** | 完整 AI 流水线 | 仅设备层面 | 仅 Ray | 批处理作业 |
| **云集成** | 多云原生 | 云中立 | 云中立 | 云中立 |
| **管理界面** | 企业级 UI | CLI/K8s | Ray Dashboard | CLI |

### Run:AI 在 EKS 上的优势

#### 1. **无缝 AWS 集成**
- **IAM 集成**: 使用 AWS IAM 进行身份验证
- **CloudWatch 集成**: 指标和日志转发到 CloudWatch
- **EBS/EFS 集成**: 数据存储与持久化

#### 2. **成本优化**
- **Spot 实例支持**: 自动使用 EC2 Spot 实例降低成本
- **自动扩缩容**: 根据工作负载需求调整节点数量
- **资源利用率优化**: 智能调度减少 GPU 闲置

#### 3. **企业级特性**
- **RBAC**: 细粒度的权限控制
- **审计日志**: 完整的安全审计
- **合规性**: 支持 SOC2、GDPR 等合规要求

### 安装和配置最佳实践

#### 生产环境配置
```bash
# 完整安装命令
helm install runai-cluster runai/runai-cluster \
  --namespace runai \
  --create-namespace \
  --set global.domain=runai.apps.cluster.example.com \
  --set runai-operator.enabled=true \
  --set runai-scheduler.enabled=true \
  --set runai-backend.enabled=true \
  --set postgresql.enabled=true \
  --set prometheus.enabled=true \
  --set grafana.enabled=true \
  --set global.ingress.enabled=true \
  --set global.ingress.className=alb \
  --set global.ingress.hosts[0]=runai.example.com
```

#### 网络配置
```yaml
# CNI 集成配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: runai-config
  namespace: runai
data:
  config.yaml: |
    cluster:
      network:
        cni: "aws-cni"  # 或 "calico", "cilium"
        mtu: 9001
    scheduler:
      gpuSharing:
        enabled: true
        strategy: "time-slicing"
```

### 总结：Run:AI 的价值

**Run:AI 重新定义了 AI 基础设施管理**：

- **AI 优先**: 专为 AI/ML 工作负载设计调度算法
- **云原生**: 深度集成主流云平台，特别是 AWS EKS
- **企业级**: 提供完整的治理、监控和安全特性
- **成本效益**: 通过智能调度和资源共享降低 TCO

在 Amazon EKS 上，**Run:AI 提供了一站式 AI 工作负载编排解决方案**，从模型训练到推理部署的全生命周期管理，让企业能够专注于 AI 创新而不是基础设施运维。

---

## KubeRay (Ray 分布式计算)

### 什么是 KubeRay？

**KubeRay** 是 Ray 分布式计算框架在 Kubernetes 上的原生集成，为大规模机器学习工作负载提供云原生支持。Ray 是一个开源的分布式计算框架，专注于 AI 和机器学习应用。

**核心特性**：
- **分布式训练**: 支持数据并行、模型并行等训练模式
- **弹性伸缩**: 根据工作负载需求自动扩缩容
- **异构资源**: 支持 CPU/GPU/TPU 等混合资源
- **生产就绪**: 提供高可用性和容错能力

### KubeRay 架构组件

#### 1. **RayCluster**
Ray 集群的核心资源，定义了头节点和工作节点。

```yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: ray-cluster
spec:
  rayVersion: '2.6.0'
  headGroupSpec:
    rayStartParams:
      block: 'true'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.6.0
          ports:
          - containerPort: 6379
          - containerPort: 8265
          - containerPort: 10001
  workerGroupSpecs:
  - groupName: gpu-workers
    replicas: 3
    minReplicas: 1
    maxReplicas: 10
    rayStartParams: {}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray-ml:2.6.3-gpu
          resources:
            limits:
              nvidia.com/gpu: 1
              cpu: "4"
              memory: "16Gi"
            requests:
              nvidia.com/gpu: 1
              cpu: "4"
              memory: "16Gi"
```

#### 2. **RayJob**
用于运行批处理作业，支持 GPU 资源分配。

```yaml
apiVersion: ray.io/v1
kind: RayJob
metadata:
  name: gpu-training-job
spec:
  rayClusterSpec:
    rayVersion: '2.6.0'
    headGroupSpec:
      rayStartParams:
        block: 'true'
      template:
        spec:
          containers:
          - name: ray-head
            image: rayproject/ray:2.6.0
  jobSpec:
    entrypoint: python train.py
    runtimeEnv: |
      pip:
        - torch
        - torchvision
    resources:
      requests:
        cpu: "2"
        memory: "4Gi"
        nvidia.com/gpu: 1
      limits:
        cpu: "4"
        memory: "8Gi"
        nvidia.com/gpu: 2
```

#### 3. **RayService**
用于部署长期运行的推理服务，支持自动扩缩容。

```yaml
apiVersion: ray.io/v1
kind: RayService
metadata:
  name: gpu-inference-service
spec:
  serviceUnhealthySecondThreshold: 300
  deploymentUnhealthySecondThreshold: 300
  rayClusterConfig:
    rayVersion: '2.6.0'
    headGroupSpec:
      rayStartParams:
        block: 'true'
      template:
        spec:
          containers:
          - name: ray-head
            image: rayproject/ray:2.6.0
    workerGroupSpecs:
    - groupName: gpu-group
      replicas: 1
      minReplicas: 1
      maxReplicas: 5
      rayStartParams: {}
      template:
        spec:
          containers:
          - name: ray-node
            image: rayproject/ray-ml:2.6.3-gpu
            resources:
              limits:
                nvidia.com/gpu: 1
  serveConfigV2: |
    applications:
    - name: gpu-app
      import_path: model:entrypoint
      runtime_env:
        pip:
          - torch
          - transformers
      deployments:
      - name: Model
        num_replicas: 2
        ray_actor_options:
          num_gpus: 0.5  # 每个副本使用 0.5 个 GPU
```

### GPU 资源管理

#### 1. **GPU 分配策略**
- **独占 GPU**: `nvidia.com/gpu: 1` - 整卡分配
- **分数 GPU**: `nvidia.com/gpu: 0.5` - GPU 分片
- **多 GPU**: `nvidia.com/gpu: 4` - 多卡分配

#### 2. **GPU 拓扑感知**
```yaml
# 节点亲和性配置
spec:
  workerGroupSpecs:
  - groupName: gpu-group
    template:
      spec:
        affinity:
          nodeAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
              nodeSelectorTerms:
              - matchExpressions:
                - key: "accelerator"
                  operator: "In"
                  values: ["nvidia-tesla-v100"]
        tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
        containers:
        - name: ray-worker
          resources:
            limits:
              nvidia.com/gpu: 1
```

#### 3. **GPU 监控**
```python
import ray
from ray.util.scheduling_strategies import NodeAffinitySchedulingStrategy

@ray.remote(num_gpus=1)
def gpu_task():
    # 获取 GPU 信息
    gpu_info = ray.get_gpu_ids()
    print(f"Allocated GPUs: {gpu_info}")

    # GPU 利用率监控
    import pynvml
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    print(f"GPU utilization: {util.gpu}%")

    return gpu_info

# 提交 GPU 任务
result = ray.get(gpu_task.remote())
```

### KubeRay 部署示例

#### 1. **安装 KubeRay Operator**
```bash
# 添加 Helm 仓库
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

# 安装 KubeRay Operator
helm install kuberay-operator kuberay/kuberay-operator \
  --namespace kuberay-system \
  --create-namespace \
  --version 0.6.0
```

#### 2. **创建 GPU Ray 集群**
```bash
kubectl apply -f - <<EOF
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: gpu-ray-cluster
  namespace: default
spec:
  rayVersion: '2.6.0'
  headGroupSpec:
    rayStartParams:
      block: 'true'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.6.0
          ports:
          - containerPort: 6379
            name: redis
          - containerPort: 8265
            name: dashboard
          - containerPort: 10001
            name: client
  workerGroupSpecs:
  - groupName: gpu-workers
    replicas: 2
    minReplicas: 1
    maxReplicas: 4
    rayStartParams: {}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray-ml:2.6.3-gpu
          resources:
            limits:
              nvidia.com/gpu: 1
              cpu: "4"
              memory: "16Gi"
          env:
          - name: CUDA_VISIBLE_DEVICES
            value: "0"
EOF
```

#### 3. **分布式训练作业**
```python
import ray
import torch
import torch.nn as nn
from ray.train import ScalingConfig
from ray.train.torch import TorchTrainer

def train_func():
    # 定义模型
    model = nn.Linear(1000, 10)

    # 数据加载器
    train_loader = torch.utils.data.DataLoader(...)

    # 训练循环
    for epoch in range(10):
        for batch in train_loader:
            # 训练逻辑
            pass

# 配置分布式训练
scaling_config = ScalingConfig(
    num_workers=4,  # 4个工作节点
    use_gpu=True,   # 使用GPU
    resources_per_worker={"GPU": 1}
)

trainer = TorchTrainer(
    train_loop_per_worker=train_func,
    scaling_config=scaling_config,
)

trainer.fit()
```

### KubeRay 优势

#### 1. **Ray 生态集成**
- **Ray Tune**: 超参数调优
- **Ray Serve**: 模型服务
- **Ray Data**: 数据处理
- **RLlib**: 强化学习

#### 2. **云原生特性**
- **Kubernetes 原生**: 完全兼容 K8s API
- **弹性伸缩**: 基于工作负载自动扩缩容
- **多租户**: 命名空间隔离和资源配额
- **监控集成**: 与 Prometheus/Grafana 集成

#### 3. **GPU 优化**
- **GPU 拓扑感知**: 优化 GPU 间通信
- **内存管理**: 高效的 GPU 内存分配
- **容错**: GPU 故障时的自动恢复

### 与其他方案对比

| 特性 | KubeRay | Run:AI | Volcano |
|-----|--------|--------|---------|
| **专注领域** | 分布式计算框架 | AI 工作负载编排 | 通用批处理调度 |
| **编程模型** | Ray Actor/Task | Kubernetes 原生 | Kubernetes 原生 |
| **扩展性** | 数千节点 | 企业级 | 通用调度 |
| **生态系统** | Ray 生态丰富 | NVIDIA 集成 | 开源社区 |

### 总结

**KubeRay 是 Ray 分布式计算框架在 Kubernetes 上的最佳实践**，提供了：

- **统一编程模型**: Actor 和 Task 抽象
- **自动扩缩容**: 基于工作负载的弹性伸缩
- **GPU 优化**: 专门的 GPU 调度和内存管理
- **生产就绪**: 高可用性和容错能力

对于需要大规模分布式 AI 训练和推理的场景，KubeRay 是不可或缺的选择。

---

## Volcano (通用批处理调度器)

### 什么是 Volcano？

**Volcano** 是华为开源的 Kubernetes 原生批处理调度系统，专为 AI、机器学习、大数据和 HPC 工作负载优化。它提供了比 Kubernetes 默认调度器更强大的资源调度和管理能力。

**核心特性**：
- **批处理调度**: 专门为批处理作业优化
- **队列管理**: 作业队列和优先级调度
- **GPU 共享**: 支持 GPU 内存和核心的精确分配
- **弹性调度**: 支持作业的弹性伸缩

### Volcano 架构组件

#### 1. **Volcano Job**
Volcano 的核心作业资源，支持复杂的批处理作业定义。

```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: gpu-training-job
spec:
  minAvailable: 4
  schedulerName: volcano
  plugins:
    ssh: []
    svc: []
  policies:
  - event: PodEvicted
    action: RestartJob
  queue: gpu-queue
  tasks:
  - replicas: 1
    name: master
    policies:
    - event: TaskCompleted
      action: CompleteJob
    template:
      spec:
        containers:
        - name: master
          image: nvcr.io/nvidia/pytorch:23.06-py3
          command: ["python", "train.py", "--role", "master"]
          resources:
            limits:
              nvidia.com/gpu: 1
              cpu: "4"
              memory: "16Gi"
  - replicas: 3
    name: worker
    template:
      spec:
        containers:
        - name: worker
          image: nvcr.io/nvidia/pytorch:23.06-py3
          command: ["python", "train.py", "--role", "worker"]
          resources:
            limits:
              nvidia.com/gpu: 1
              cpu: "4"
              memory: "16Gi"
```

#### 2. **Queue (队列)**
作业队列管理，支持优先级和资源配额。

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: gpu-queue
spec:
  weight: 1
  reclaimable: false
  capability:
    cpu: "100"
    memory: "400Gi"
    nvidia.com/gpu: "16"
```

#### 3. **PodGroup**
用于管理一组相关 Pod 的调度约束。

```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: gpu-podgroup
spec:
  minMember: 4
  queue: gpu-queue
```

### GPU 资源调度

#### 1. **GPU 卡数分配**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
  labels:
    volcano.sh/task-index: "0"
spec:
  schedulerName: volcano
  containers:
  - name: gpu-container
    image: nvidia/cuda:11.8-runtime-ubuntu20.04
    resources:
      limits:
        volcano.sh/gpu-number: 2  # 请求2个GPU
```

#### 2. **GPU 内存分配**
```yaml
resources:
  limits:
    volcano.sh/gpu-memory: 4096  # 请求4096MB GPU内存
```

#### 3. **GPU 核心分配**
```yaml
resources:
  limits:
    volcano.sh/gpu-cores: 50  # 请求50%的GPU核心
```

### Volcano 高级特性

#### 1. **插件系统**
- **SSH 插件**: 提供容器间 SSH 通信
- **SVC 插件**: 服务发现和负载均衡
- **ENV 插件**: 环境变量注入
- **MPI 插件**: MPI 作业支持

#### 2. **作业生命周期管理**
- **抢占**: 高优先级作业可抢占低优先级作业
- **重调度**: 根据集群状态重新调度作业
- **容错**: 作业失败时的自动恢复

#### 3. **队列调度**
```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: gpu-queue
spec:
  weight: 10  # 队列权重
  capability:
    nvidia.com/gpu: "8"
  state: Open  # Open/Closed/Closing
```

### Volcano 部署配置

#### 1. **安装 Volcano**
```bash
# 添加 Helm 仓库
helm repo add volcano-sh https://volcano-sh.github.io/helm-charts
helm repo update

# 安装 Volcano
helm install volcano volcano-sh/volcano \
  --namespace volcano-system \
  --create-namespace \
  --version 1.8.0
```

#### 2. **配置 Admission Controller**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: volcano-admission-configmap
  namespace: volcano-system
data:
  volcano-admission.conf: |
    resourceGroups:
    - resourceGroup: gpu
      object:
        key: annotation
        value:
        - "volcano.sh/resource-group: gpu"
      schedulerName: volcano
      labels:
        volcano.sh/nodetype: gpu
```

#### 3. **GPU 节点配置**
```yaml
# 为 GPU 节点添加标签
kubectl label nodes gpu-node-01 volcano.sh/nodetype=gpu
kubectl label nodes gpu-node-01 accelerator=nvidia-tesla-v100

# 添加污点（可选）
kubectl taint nodes gpu-node-01 nvidia.com/gpu=present:NoSchedule
```

### Volcano GPU 作业示例

#### 1. **分布式训练作业**
```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: distributed-training
spec:
  minAvailable: 4
  schedulerName: volcano
  plugins:
    ssh: []
    svc: []
  queue: gpu-queue
  tasks:
  - replicas: 1
    name: ps
    template:
      spec:
        containers:
        - name: tensorflow
          image: tensorflow/tensorflow:2.12.0-gpu
          command: ["python", "ps.py"]
          resources:
            limits:
              nvidia.com/gpu: 1
  - replicas: 3
    name: worker
    template:
      spec:
        containers:
        - name: tensorflow
          image: tensorflow/tensorflow:2.12.0-gpu
          command: ["python", "worker.py"]
          resources:
            limits:
              nvidia.com/gpu: 1
```

#### 2. **MPI 作业**
```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: mpi-gpu-job
spec:
  minAvailable: 3
  schedulerName: volcano
  plugins:
    ssh: []
    svc: []
  tasks:
  - replicas: 1
    name: mpimaster
    template:
      spec:
        containers:
        - command: ["/bin/bash", "-c", "mpirun -np 2 -H worker-0,worker-1 python mpi_train.py"]
          image: nvcr.io/nvidia/pytorch:23.06-py3
          resources:
            limits:
              nvidia.com/gpu: 1
  - replicas: 2
    name: mpiworker
    template:
      spec:
        containers:
        - command: ["/bin/bash", "-c", "sleep 3600"]
          image: nvcr.io/nvidia/pytorch:23.06-py3
          resources:
            limits:
              nvidia.com/gpu: 1
```

### Volcano 监控与调试

#### 1. **Volcano Dashboard**
```bash
# 安装 Volcano Dashboard
helm install volcano-dashboard volcano-sh/volcano-dashboard \
  --namespace volcano-system
```

#### 2. **作业状态监控**
```bash
# 查看作业状态
kubectl get vcjob

# 查看 Pod 状态
kubectl get pods -l volcano.sh/job-name=your-job

# 查看队列状态
kubectl get queue
```

#### 3. **调度器日志**
```bash
# 查看调度器日志
kubectl logs -n volcano-system deployment/volcano-scheduler

# 查看控制器日志
kubectl logs -n volcano-system deployment/volcano-controller
```

### Volcano 优势

#### 1. **批处理优化**
- **队列管理**: 作业队列和优先级调度
- **资源保证**: 为批处理作业提供稳定的资源分配
- **弹性伸缩**: 根据队列负载自动调整资源

#### 2. **AI/HPC 优化**
- **组调度**: 支持 gang scheduling（一组 Pod 同时调度）
- **拓扑感知**: 考虑网络和存储拓扑进行调度
- **容错恢复**: 作业失败时的自动重试和恢复

#### 3. **企业级特性**
- **多租户**: 命名空间级别的资源隔离
- **配额管理**: 队列级别的资源配额
- **审计日志**: 完整的作业执行审计

### 与其他方案对比

| 特性 | Volcano | KubeRay | Run:AI | Kubernetes 默认 |
|-----|---------|---------|--------|----------------|
| **调度类型** | 批处理优先 | 分布式计算 | AI 编排 | 通用调度 |
| **GPU 支持** | 完整的 GPU 调度 | Ray GPU 管理 | NVIDIA 优化 | 基础 GPU 分配 |
| **队列管理** | 高级队列 | 简单队列 | 项目配额 | 无队列 |
| **伸缩能力** | 企业级 | 大规模 | 企业级 | 基础 |

### 总结

**Volcano 是 Kubernetes 上批处理作业调度的最佳选择**，提供了：

- **强大的批处理调度**: 专门为批处理作业优化
- **GPU 精细控制**: 支持 GPU 内存、核心的精确分配
- **企业级管理**: 队列、配额、优先级的完整管理
- **高度可扩展**: 支持大规模集群的作业调度

对于需要运行大规模批处理 AI 训练、HPC 计算的企业，Volcano 是不可或缺的调度基础设施。

---

## 云服务商 GPU 调度

### AWS EKS GPU 调度

AWS EKS 提供了完整的 GPU 支持，包括 P4d、P3、G4dn、G5 等实例类型。

#### GPU 节点组配置

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: gpu-cluster
  region: us-west-2
managedNodeGroups:
- name: gpu-nodes
  instanceType: p3.2xlarge
  minSize: 1
  maxSize: 3
  labels:
    accelerator: nvidia-tesla-v100
  taints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
```

#### EKS GPU 工作负载示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod-eks
spec:
  containers:
  - name: tensorflow
    image: tensorflow/tensorflow:latest-gpu
    command: ["python", "train.py"]
    resources:
      limits:
        nvidia.com/gpu: 1
        memory: "16Gi"
        cpu: "4"
  nodeSelector:
    accelerator: nvidia-tesla-v100
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

### GCP GKE GPU 调度

Google Cloud GKE 提供 A100、V100、T4 等 GPU 支持。

#### GKE GPU 节点池

```bash
# 创建GPU节点池
gcloud container node-pools create gpu-pool \
  --cluster=gpu-cluster \
  --machine-type=n1-standard-8 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --num-nodes=1 \
  --min-nodes=0 \
  --max-nodes=3
```

#### GKE GPU Pod 示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod-gke
spec:
  containers:
  - name: gpu-container
    image: gcr.io/deeplearning-platform-release/tf2-gpu
    resources:
      limits:
        nvidia.com/gpu: 1
  nodeSelector:
    cloud.google.com/gke-accelerator: nvidia-tesla-t4
```

### Azure AKS GPU 调度

Azure AKS 支持 NC、ND 系列 GPU 实例。

#### AKS GPU 节点池

```bash
# 创建GPU节点池
az aks nodepool add \
  --resource-group myResourceGroup \
  --cluster-name myAKSCluster \
  --name gpunp \
  --node-count 1 \
  --node-vm-size Standard_NC6 \
  --node-taints sku=gpu:NoSchedule \
  --aks-custom-headers UseGPUDedicatedVHD=true
```

#### AKS GPU 工作负载

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod-aks
spec:
  containers:
  - name: gpu-container
    image: mcr.microsoft.com/azureml/openmpi4.1.0-cuda11.6-cudnn8-ubuntu20.04-py38:v0.1.0
    resources:
      limits:
        nvidia.com/gpu: 1
  tolerations:
  - key: sku
    operator: Equal
    value: gpu
    effect: NoSchedule
  nodeSelector:
    accelerator: nvidia-tesla-k80
```

## AMD GPU Operator

AMD 提供了自己的 GPU Operator 来管理 AMD GPU 资源。

### 安装 AMD GPU Operator

```bash
# 添加 AMD Helm 仓库
helm repo add amd-gpu https://amd.github.io/gpu-operator
helm repo update

# 安装 AMD GPU Operator
helm install amd-gpu-operator amd-gpu/gpu-operator \
  --namespace gpu-operator \
  --create-namespace
```

### AMD GPU 调度示例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: amd-gpu-pod
spec:
  containers:
  - name: amd-gpu-container
    image: rocm/tensorflow:latest
    command: ["python", "train.py"]
    resources:
      limits:
        amd.com/gpu: 1
  nodeSelector:
    amd.com/gpu.family: "Navi21"
```

## Intel GPU 调度

Intel 提供 GPU device plugin 支持 Intel 集成显卡和独立 GPU。

### Intel GPU Device Plugin

```bash
# 部署 Intel GPU 插件
kubectl apply -f https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/main/deployments/gpu_plugin/base/intel-gpu-plugin.yaml
```

### Intel GPU 工作负载

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: intel-gpu-pod
spec:
  containers:
  - name: intel-gpu-container
    image: intel/oneapi-basekit:latest
    resources:
      limits:
        gpu.intel.com/i915: 1  # Intel 集成显卡
        # 或
        gpu.intel.com/igpu: 1   # Intel 独立GPU
```

## MGS (Multi-Granularity GPU Scheduling)

MGS (Multi-Granularity GPU Scheduling) 是一个多粒度 GPU 调度框架的概念，主要关注在不同粒度级别上进行 GPU 资源的分配和管理。

### MGS 概念说明

MGS 不是一个具体的开源实现，而是一个研究性的 GPU 调度框架概念，主要包含以下层次：

#### 1. **作业级调度 (Job-level Scheduling)**
- 决定哪些作业可以获得 GPU 资源
- 基于作业优先级、资源需求进行决策

#### 2. **任务级调度 (Task-level Scheduling)**
- 在作业内部分配 GPU 给具体任务
- 考虑任务间的依赖关系和通信模式

#### 3. **操作级调度 (Operation-level Scheduling)**
- 在具体操作层面优化 GPU 使用
- 考虑内存访问模式、计算密度等

### MGS 实现状态

目前，MGS 主要存在于学术研究中，还没有成熟的开源实现。如果您指的是某个特定实现，请提供更多详细信息。

在实际生产环境中，可以通过以下方式实现类似的多粒度调度：

#### 使用 Kubernetes 原生功能

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-granularity-gpu-pod
  annotations:
    # 作业级配置
    gpu-scheduler/job-priority: "high"
    # 任务级配置
    gpu-scheduler/task-affinity: "compute-intensive"
spec:
  containers:
  - name: gpu-worker
    resources:
      limits:
        nvidia.com/gpu: 1
        # 操作级配置通过环境变量传递
    env:
    - name: GPU_MEMORY_FRACTION
      value: "0.8"
    - name: GPU_CORE_FRACTION
      value: "0.6"
```

#### 使用 Volcano 高级调度

```yaml
apiVersion: batch.volcano.sh/v1alpha1
kind: Job
metadata:
  name: mgs-style-job
spec:
  schedulerName: volcano
  policies:
  - event: PodEvicted
    action: RestartJob
  tasks:
  - replicas: 2
    name: gpu-task
    template:
      spec:
        containers:
        - name: gpu-container
          resources:
            limits:
              volcano.sh/vgpu-number: 1
              volcano.sh/vgpu-memory: 4096
              volcano.sh/vgpu-cores: 50
        restartPolicy: OnFailure
```

## GPU 时间切片 (Time Slicing)

Time Slicing 允许在同一物理 GPU 上运行多个工作负载，实现 GPU 资源共享。

### 基本概念

- **Time Slicing**: 通过时间多路复用来共享 GPU
- **MIG**: 通过硬件分区来隔离 GPU 资源
- **资源复制**: 将一个物理 GPU 虚拟化为多个逻辑 GPU

### Time Slicing 配置

#### 1. 创建 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: time-slicing-config
  namespace: gpu-operator
data:
  any: |
    version: v1
    flags:
      migStrategy: none
    sharing:
      timeSlicing:
        renameByDefault: false
        failRequestsGreaterThanOne: false
        resources:
        - name: nvidia.com/gpu
          replicas: 4
```

#### 2. 应用配置

```bash
# 创建 ConfigMap
kubectl apply -f time-slicing-config.yaml -n gpu-operator

# 更新 ClusterPolicy
kubectl patch clusterpolicies.nvidia.com/cluster-policy \
  -n gpu-operator --type merge \
  -p '{"spec": {"devicePlugin": {"config": {"name": "time-slicing-config", "default": "any"}}}}'
```

#### 3. 验证配置

```bash
# 检查节点标签变化
kubectl describe node <node-name> | grep nvidia.com/gpu

# 示例输出：
# nvidia.com/gpu.replicas=4
# nvidia.com/gpu.product=Tesla-T4-SHARED
# Capacity: nvidia.com/gpu: 16  # 4个物理GPU × 4个副本
```

### 使用 Time Slicing GPU

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: time-slicing-demo
spec:
  replicas: 8  # 超过物理GPU数量
  selector:
    matchLabels:
      app: time-slicing-demo
  template:
    metadata:
      labels:
        app: time-slicing-demo
    spec:
      containers:
      - name: cuda-workload
        image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda11.7.1-ubuntu20.04
        command: ["/bin/bash", "-c", "--"]
        args: ["while true; do /cuda-samples/vectorAdd; done"]
        resources:
          limits:
            nvidia.com/gpu: 1
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```

## MIG (Multi-Instance GPU)

MIG 允许将单个 GPU 物理划分为多个独立的 GPU 实例，每个实例都有自己的内存和计算资源。

### MIG 策略

- **none**: 不使用 MIG
- **single**: 所有 GPU 使用相同的 MIG 配置
- **mixed**: 不同 GPU 使用不同的 MIG 配置

### MIG 配置示例

#### 1. 启用 MIG

```bash
# 设置 MIG 策略为 single
kubectl patch clusterpolicies.nvidia.com/cluster-policy \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/mig/strategy", "value": "single"}]'
```

#### 2. 配置 MIG Profile

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mig-config
  namespace: gpu-operator
data:
  config.yaml: |
    version: v1
    mig-configs:
      all-disabled:
        - devices: all
          mig-enabled: false
      all-1g.10gb:
        - devices: all
          mig-enabled: true
          mig-devices:
            "1g.10gb": 2  # 2个 1g.10gb MIG 实例
      all-2g.20gb:
        - devices: all
          mig-enabled: true
          mig-devices:
            "2g.20gb": 3  # 3个 2g.20gb MIG 实例
```

#### 3. 应用 MIG 配置

```bash
# 应用配置
kubectl apply -f mig-config.yaml -n gpu-operator

# 更新 ClusterPolicy
kubectl patch clusterpolicies.nvidia.com/cluster-policy \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/migManager/config/name", "value": "mig-config"}]'

# 标记节点使用特定配置
kubectl label nodes <node-name> nvidia.com/mig.config=all-1g.10gb --overwrite
```

#### 4. 使用 MIG 实例

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mig-workload
spec:
  restartPolicy: OnFailure
  containers:
  - name: cuda-workload
    image: nvidia/samples:vectoradd-cuda11.2.1
    resources:
      limits:
        nvidia.com/mig-1g.10gb: 1  # 请求 MIG 实例
  nodeSelector:
    nvidia.com/gpu.product: A100-SXM4-40GB-MIG-1g.10gb
```

### MIG 实例类型

| MIG Profile | Memory | SM Count | Tensor Cores |
|-------------|--------|----------|--------------|
| 1g.5gb     | 5GB    | 14       | 14          |
| 1g.10gb    | 10GB   | 14       | 14          |
| 2g.10gb    | 10GB   | 28       | 28          |
| 2g.20gb    | 20GB   | 28       | 28          |
| 3g.20gb    | 20GB   | 42       | 42          |
| 3g.40gb    | 40GB   | 42       | 42          |
| 7g.40gb    | 40GB   | 98       | 98          |

## 高级调度策略

### 节点亲和性调度

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-affinity-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: "nvidia.com/gpu.product"
            operator: In
            values: ["Tesla-V100", "Tesla-T4"]
          - key: "nvidia.com/gpu.memory"
            operator: Gt
            values: ["8000"]  # 至少8GB GPU内存
  containers:
  - name: gpu-app
    image: my-gpu-app:latest
    resources:
      limits:
        nvidia.com/gpu: 1
```

### GPU 内存感知调度

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-memory-aware
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: "nvidia.com/gpu.count"
            operator: Gt
            values: ["1"]  # 至少2个GPU的节点
  containers:
  - name: gpu-app
    image: my-gpu-app:latest
    resources:
      limits:
        nvidia.com/gpu: 1
        memory: "16Gi"  # 确保有足够的系统内存
```

### 多 GPU 调度

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-gpu-pod
spec:
  containers:
  - name: multi-gpu-app
    image: my-multi-gpu-app:latest
    resources:
      limits:
        nvidia.com/gpu: 2  # 请求2个GPU
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: "nvidia.com/gpu.count"
            operator: Gt
            values: ["1"]  # 确保节点至少有2个GPU
```

## 实际使用案例

### 案例 1: 机器学习训练

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ml-training-job
spec:
  restartPolicy: OnFailure
  containers:
  - name: pytorch-training
    image: pytorch/pytorch:1.9.0-cuda11.1-cudnn8-runtime
    command: ["python", "train.py"]
    resources:
      limits:
        nvidia.com/gpu: 1
        memory: "32Gi"
        cpu: "8"
    volumeMounts:
    - name: training-data
      mountPath: /data
  volumes:
  - name: training-data
    persistentVolumeClaim:
      claimName: training-data-pvc
  nodeSelector:
    gpu-type: training-optimized
```

### 案例 2: GPU 推理服务

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gpu-inference-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gpu-inference
  template:
    metadata:
      labels:
        app: gpu-inference
    spec:
      containers:
      - name: inference-server
        image: nvcr.io/nvidia/tritonserver:21.08-py3
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /v2/health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference:
              matchExpressions:
              - key: gpu-type
                operator: In
                values: ["inference-optimized"]
```

### 案例 3: GPU 时间切片共享

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shared-gpu-workloads
spec:
  replicas: 10  # 超过物理GPU数量
  selector:
    matchLabels:
      app: shared-gpu-app
  template:
    metadata:
      labels:
        app: shared-gpu-app
    spec:
      containers:
      - name: gpu-workload
        image: nvidia/cuda:11.2-base-ubuntu20.04
        command: ["python3", "-c"]
        args:
        - |
          import torch
          import time
          device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
          while True:
              x = torch.randn(1000, 1000).to(device)
              y = torch.matmul(x, x)
              time.sleep(1)
        resources:
          limits:
            nvidia.com/gpu: 1  # 共享GPU
            memory: "2Gi"
            cpu: "1"
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
```

## 监控和故障排除

### GPU 资源监控

```bash
# 查看节点 GPU 资源分配
kubectl describe node <node-name> | grep -A 10 "Allocated resources"

# 查看 Pod GPU 使用情况
kubectl get pods -o custom-columns=NAME:.metadata.name,GPU:.spec.containers[*].resources.limits

# NVIDIA SMI 监控
kubectl exec -it <gpu-pod> -- nvidia-smi

# DCGM 监控指标
kubectl get servicemonitor -n gpu-operator
```

### 常见问题排查

#### 1. Pod 无法调度到 GPU 节点

```bash
# 检查节点 GPU 标签
kubectl describe node <node-name> | grep nvidia.com

# 检查 Pod 事件
kubectl describe pod <pod-name>

# 检查 GPU Operator 日志
kubectl logs -n gpu-operator deployment/gpu-operator
```

#### 2. GPU 内存不足

```bash
# 检查 GPU 内存使用
kubectl exec -it <gpu-pod> -- nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# 调整 Pod 资源限制
kubectl edit pod <pod-name>
```

#### 3. GPU 设备插件错误

```bash
# 检查设备插件状态
kubectl get pods -n gpu-operator -l app=nvidia-device-plugin-daemonset

# 查看设备插件日志
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
```

### 性能监控

#### Prometheus 监控配置

```yaml
# DCGM Exporter ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: gpu-metrics
  namespace: gpu-operator
spec:
  selector:
    matchLabels:
      app: nvidia-dcgm-exporter
  endpoints:
  - port: metrics
    interval: 15s
```

#### 关键指标

- `DCGM_FI_DEV_GPU_UTIL`: GPU 利用率
- `DCGM_FI_DEV_MEM_COPY_UTIL`: 内存复制利用率
- `DCGM_FI_DEV_FB_USED`: GPU 内存使用量
- `DCGM_FI_DEV_SM_CLOCK`: SM 时钟频率

## 最佳实践

### 1. 资源规划

- **GPU 选择**: 根据工作负载选择合适的 GPU 类型
- **资源配比**: GPU:CPU:内存 = 1:4-8:16-32GB
- **节点分组**: 将不同类型的 GPU 工作负载分离

### 2. 调度策略

- **亲和性**: 使用节点亲和性确保工作负载调度到合适的 GPU
- **污点容忍**: 为 GPU 节点设置污点，防止非 GPU 工作负载调度
- **优先级**: 为重要工作负载设置优先级

### 3. 资源管理

- **限制设置**: 始终设置资源 limits，防止资源争用
- **预留资源**: 为系统组件预留 GPU 资源
- **监控告警**: 设置 GPU 利用率和内存使用告警

### 4. 安全考虑

- **命名空间隔离**: 使用命名空间隔离不同团队的 GPU 资源
- **RBAC**: 配置适当的 RBAC 权限控制 GPU 访问
- **资源配额**: 设置命名空间级别的 GPU 资源配额

### 5. 故障恢复

- **健康检查**: 配置 Pod 存活探针和就绪探针
- **自动重启**: 设置适当的重启策略
- **备份策略**: 为 GPU 工作负载配置备份和恢复策略

### 配置示例：生产环境 GPU 集群

```yaml
# ClusterPolicy for production
apiVersion: nvidia.com/v1
kind: ClusterPolicy
metadata:
  name: gpu-cluster-policy
spec:
  dcgm:
    enabled: true
    config:
      name: dcgm-config
  dcgmExporter:
    config:
      name: dcgm-exporter-config
  devicePlugin:
    config:
      name: device-plugin-config
  driver:
    enabled: true
    version: "550.54.15"  # 指定驱动版本
  gfd:
    enabled: true
  migManager:
    enabled: true
    config:
      name: mig-manager-config
  operator:
    defaultRuntime: containerd
  toolkit:
    enabled: true
  validator:
    plugin:
      env:
      - name: WITH_WORKLOAD
        value: "true"
```

## GPU 加速基础概念

### 什么是 GPU 加速？

GPU 加速是指**使用 GPU (Graphics Processing Unit) 来执行原本在 CPU 上运行的计算任务**，以获得更高的性能和效率。

**核心思想**：将适合并行处理的计算任务从 CPU 转移到 GPU，利用 GPU 大量的计算核心实现并行加速。

### CPU vs GPU 架构对比

| 特性 | CPU (Central Processing Unit) | GPU (Graphics Processing Unit) |
|-----|------------------------------|-------------------------------|
| **核心数量** | 4-64 个核心 | 数千-数万个核心 |
| **核心类型** | 通用核心 (CPU cores) | 专用核心 (CUDA cores/Stream processors) |
| **架构设计** | SISD/SIMD (串行/轻度并行) | SIMD/MIMD (大规模并行) |
| **内存带宽** | 50-100 GB/s | 数百-数TB/s |
| **延迟优化** | 低延迟 | 高吞吐量 |
| **擅长任务** | 复杂逻辑、分支判断、通用计算 | 大规模并行计算、矩阵运算、浮点计算 |
| **功耗设计** | 平衡性能与功耗 | 最大化计算密度 |

### GPU 加速的工作原理

#### 1. **CUDA 编程模型**
```cpp
// CUDA 内核函数 - 在GPU上并行执行
__global__ void vectorAdd(float* a, float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        c[i] = a[i] + b[i];
    }
}

// CPU 端调用
int main() {
    float *a, *b, *c;  // CPU 内存
    float *d_a, *d_b, *d_c;  // GPU 设备内存

    // 分配GPU内存
    cudaMalloc(&d_a, size);
    cudaMalloc(&d_b, size);
    cudaMalloc(&d_c, size);

    // 从CPU复制数据到GPU
    cudaMemcpy(d_a, a, size, cudaMemcpyHostToDevice);
    cudaMemcpy(d_b, b, size, cudaMemcpyHostToDevice);

    // 启动GPU内核 (假设有N个元素，256线程/块)
    int blocks = (N + 255) / 256;
    vectorAdd<<<blocks, 256>>>(d_a, d_b, d_c, N);

    // 从GPU复制结果回CPU
    cudaMemcpy(c, d_c, size, cudaMemcpyDeviceToHost);

    // 释放GPU内存
    cudaFree(d_a);
    cudaFree(d_b);
    cudaFree(d_c);
}
```

#### 2. **GPU 线程层次结构**
```
Grid (网格)
├── Block 0 (块)
│   ├── Thread 0,0
│   ├── Thread 0,1
│   └── ...
├── Block 1
│   ├── Thread 1,0
│   ├── Thread 1,1
│   └── ...
└── ...
```

- **Thread**: 最基本的执行单位
- **Block**: 线程块，共享内存空间
- **Grid**: 整个内核的执行空间

### GPU 加速的应用场景

#### 1. **深度学习训练**
```python
import torch

# GPU加速的张量运算
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 数据移动到GPU
x = torch.randn(1000, 1000).to(device)
y = torch.randn(1000, 1000).to(device)

# GPU并行矩阵乘法
z = torch.matmul(x, y)  # 在GPU上执行，速度比CPU快10-100倍

# 神经网络前向传播
output = model(input.to(device))  # 整个网络在GPU上运行
```

#### 2. **科学计算**
- **分子动力学模拟**: 计算原子间相互作用
- **天气预报**: 数值天气预测模型
- **流体力学**: CFD (Computational Fluid Dynamics)
- **量子化学**: 分子轨道计算

#### 3. **图像和视频处理**
- **图像卷积**: 滤波、边缘检测、特征提取
- **视频编码/解码**: H.264, H.265 硬件加速
- **计算机视觉**: 目标检测、图像分割、姿态估计

#### 4. **金融计算**
- **期权定价**: Monte Carlo 模拟
- **风险建模**: VaR (Value at Risk) 计算
- **高频交易**: 实时数据分析

#### 5. **数据库加速**
- **查询加速**: GPU 加速的数据库查询
- **分析计算**: 大数据分析和聚合操作
- **机器学习**: 数据库内嵌的 ML 推理

### GPU 加速的性能优势

#### 1. **理论性能对比**
- **单精度浮点**: GPU 比 CPU 快 10-50 倍
- **双精度浮点**: GPU 比 CPU 快 5-10 倍
- **整数运算**: GPU 比 CPU 快 5-20 倍

#### 2. **实际应用性能提升**
| 应用领域 | 典型加速倍数 | 说明 |
|---------|-------------|------|
| 深度学习训练 | 10-100x | ResNet-50, BERT 等模型 |
| 图像处理 | 50-500x | 卷积神经网络推理 |
| 科学计算 | 20-200x | 分子动力学, 天气模拟 |
| 视频处理 | 10-50x | H.264/H.265 编解码 |

#### 3. **能效优势**
- GPU 在并行计算中的能效比 CPU 高 2-5 倍
- 相同性能下，GPU 功耗更低

### GPU 编程框架

#### 1. **CUDA (NVIDIA)**
```cpp
// NVIDIA GPU编程框架
__global__ void kernel(float* data) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    // 并行计算逻辑
}
```

#### 2. **HIP (AMD)**
```cpp
// AMD GPU编程框架，类似CUDA
__global__ void kernel(float* data) {
    int idx = hipBlockIdx_x * hipBlockDim_x + hipThreadIdx_x;
    // 并行计算逻辑
}
```

#### 3. **OpenCL (跨平台)**
```cpp
// 跨厂商GPU编程标准
__kernel void kernel(__global float* data) {
    int idx = get_global_id(0);
    // 并行计算逻辑
}
```

#### 4. **深度学习框架**
```python
# PyTorch GPU加速
import torch
model = MyModel().cuda()  # 模型移动到GPU
optimizer = torch.optim.Adam(model.parameters())

for batch in dataloader:
    inputs, labels = batch
    inputs, labels = inputs.cuda(), labels.cuda()  # 数据移动到GPU

    optimizer.zero_grad()
    outputs = model(inputs)  # GPU计算
    loss = criterion(outputs, labels)
    loss.backward()  # GPU反向传播
    optimizer.step()  # GPU参数更新
```

### GPU 加速的挑战与解决方案

#### 1. **内存传输开销**
```cpp
// 解决方案：异步内存复制和统一内存
cudaStream_t stream;
cudaStreamCreate(&stream);

// 异步内存复制
cudaMemcpyAsync(d_data, h_data, size, cudaMemcpyHostToDevice, stream);

// GPU计算与传输并行
kernel<<<grid, block, 0, stream>>>(d_data);
```

#### 2. **CPU-GPU 同步**
```cpp
// 解决方案：事件同步和流
cudaEvent_t event;
cudaEventCreate(&event);
cudaEventRecord(event, stream);
// 等待GPU完成
cudaEventSynchronize(event);
```

#### 3. **GPU 资源管理**
- **多GPU管理**: NCCL 进行 GPU 间通信
- **内存管理**: 统一内存和内存池
- **错误处理**: CUDA 运行时错误检查

### GPU 加速的发展趋势

#### 1. **异构计算**
- CPU + GPU 协同计算
- 智能任务调度到最适合的处理器

#### 2. **AI 加速器**
- TPU (Google), NPU (华为), IPU (Graphcore)
- 专用 AI 芯片，针对神经网络优化

#### 3. **量子加速**
- 量子计算机与传统 GPU 的结合
- 混合量子-经典计算

#### 4. **边缘计算**
- 边缘设备上的 GPU 加速
- 实时 AI 推理

### 总结：GPU 加速的价值

GPU 加速代表了**现代计算架构的重大转变**：

- **从串行到并行**: 利用数千核心实现大规模并行
- **从通用到专用**: 为特定计算模式优化硬件
- **从单机到分布式**: GPU 集群实现超大规模计算
- **从科学计算到 AI**: 深度学习推动 GPU 加速的普及

**核心洞察**: GPU 加速不是简单的"提速"，而是**计算范式的根本改变**，让原本不可能的计算任务变为可能。

---

## GPU 通信与网络

### NCCL (NVIDIA Collective Communications Library)

NCCL 是 NVIDIA 开发的用于 GPU 间高效通信的库，支持多种通信模式和网络协议。**重要澄清：NCCL 不是直接的 GPU 加速库，而是用于优化多 GPU 间通信效率的库**。它通过高效的集体通信原语来减少分布式训练中的通信开销，从而间接提升训练性能。

**NCCL ≠ GPU加速器**
- NCCL 不执行 GPU 计算加速
- NCCL 优化 GPU 之间的数据传输
- NCCL 使多 GPU 分布式训练成为可能

**NCCL 在深度学习中的作用**：
- AllReduce 操作同步梯度更新
- 多 GPU 间高效参数同步
- 减少通信延迟，提升训练速度

#### NCCL 核心特性

- **集体通信原语**: AllReduce, AllGather, ReduceScatter, Broadcast 等
- **拓扑感知**: 自动检测硬件拓扑并优化通信路径选择
- **多协议支持**: PCIe, NVLink, NVSwitch, InfiniBand Verbs, TCP/IP sockets
- **自动路径选择**: 根据可用硬件自动选择最优通信协议
- **异步通信**: 非阻塞通信操作，支持CUDA流集成
- **单内核实现**: 每个集体操作都在单个GPU内核中完成通信和计算

#### NCCL 在分布式训练中的作用

```python
# 典型的使用场景：梯度同步
# 每个GPU计算完梯度后，使用NCCL进行AllReduce同步

# 传统方式：CPU协调通信
# gradients -> CPU -> 网络 -> 其他GPU (慢且占用CPU)

# NCCL方式：GPU直接通信
# gradients -> NCCL AllReduce -> 同步梯度 (快且不占用CPU)

# 结果：训练速度提升数倍
```

**为什么 NCCL 对分布式训练至关重要**：
- 梯度同步是训练瓶颈
- NCCL 将通信时间从秒级降到毫秒级
- 支持数千GPU的大规模训练

#### NCCL 通信原语

| 原语 | 描述 | 输入/输出 |
|-----|------|----------|
| **AllReduce** | 所有GPU数据规约后广播 | N → N |
| **AllGather** | 收集所有GPU数据到所有GPU | N → N×N |
| **ReduceScatter** | 规约后分散数据 | N → N |
| **Broadcast** | 从一个GPU广播到所有GPU | 1 → N |
| **Send/Recv** | 点对点通信 | 1 → 1 |

#### NCCL 通信协议详解

NCCL 支持多种底层通信协议，并根据硬件拓扑自动选择最优路径：

| 通信协议 | 适用场景 | 延迟 | 带宽 | 特点 |
|---------|---------|------|------|------|
| **NVLink** | GPU间直连 | ~1.5ns | 50-600 GB/s | 最高性能，硬件级隔离 |
| **PCIe** | GPU到CPU/网卡 | ~1μs | 16-128 GB/s | 标准接口，通用性强 |
| **InfiniBand** | 节点间通信 | <1μs | 100-400 Gbps | 低延迟，高吞吐 |
| **TCP/IP** | 通用网络 | 10-100μs | 10-100 Gbps | 兼容性好，易部署 |

**通信路径选择逻辑**：
1. 优先使用 NVLink（如果GPU间存在NVLink连接）
2. 使用 PCIe + InfiniBand（跨节点通信）
3. 回退到 TCP/IP（兼容性兜底）

**拓扑感知机制**：
- NCCL 会自动检测硬件拓扑
- 根据 GPU 间距离和连接类型选择最优路径
- 支持树形、环形等多种通信模式
- 动态调整通信策略以优化性能

**NCCL 对分布式训练性能的影响**：

| 通信协议 | 8GPU AllReduce时间 | 对比 PCIe |
|---------|-------------------|----------|
| PCIe | ~100ms | 1x |
| NVLink | ~10ms | 10x 提升 |
| InfiniBand | ~5ms | 20x 提升 |

*数据为典型值，实际性能取决于具体硬件配置*

#### NCCL 单机多卡示例

```c
#include "nccl.h"
#include "cuda_runtime.h"

int main() {
    int num_gpus = 4;
    ncclComm_t comms[4];
    cudaStream_t streams[4];

    // 初始化 NCCL 通信器
    ncclUniqueId id;
    ncclGetUniqueId(&id);

    for (int i = 0; i < num_gpus; i++) {
        cudaSetDevice(i);
        cudaStreamCreate(&streams[i]);
        ncclCommInitRank(&comms[i], num_gpus, id, i);
    }

    // AllReduce 示例
    size_t count = 1024 * 1024;
    float* sendbuff[4], *recvbuff[4];

    for (int i = 0; i < num_gpus; i++) {
        cudaSetDevice(i);
        cudaMalloc(&sendbuff[i], count * sizeof(float));
        cudaMalloc(&recvbuff[i], count * sizeof(float));
        // 初始化数据...
    }

    // 执行 AllReduce
    ncclGroupStart();
    for (int i = 0; i < num_gpus; i++) {
        ncclAllReduce((const void*)sendbuff[i], (void*)recvbuff[i],
                     count, ncclFloat, ncclSum, comms[i], streams[i]);
    }
    ncclGroupEnd();

    // 同步并清理
    for (int i = 0; i < num_gpus; i++) {
        cudaSetDevice(i);
        cudaStreamSynchronize(streams[i]);
        ncclCommDestroy(comms[i]);
        cudaFree(sendbuff[i]);
        cudaFree(recvbuff[i]);
    }

    return 0;
}
```

#### NCCL 多机多卡示例 (MPI)

```c
#include "nccl.h"
#include "mpi.h"
#include "cuda_runtime.h"

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // 计算本地GPU ID
    int local_rank = rank % 4;  // 假设每节点4个GPU
    int local_size = 4;

    cudaSetDevice(local_rank);

    // 生成唯一ID (仅root进程)
    ncclUniqueId id;
    if (rank == 0) {
        ncclGetUniqueId(&id);
    }
    MPI_Bcast(&id, sizeof(ncclUniqueId), MPI_BYTE, 0, MPI_COMM_WORLD);

    // 初始化通信器
    ncclComm_t comm;
    ncclCommInitRank(&comm, size, id, rank);

    // 创建CUDA流
    cudaStream_t stream;
    cudaStreamCreate(&stream);

    // 执行分布式训练...
    // ncclAllReduce(...)

    ncclCommDestroy(comm);
    cudaStreamDestroy(stream);
    MPI_Finalize();

    return 0;
}
```

#### NCCL 在 Kubernetes 中的使用

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nccl-multi-gpu-training
spec:
  containers:
  - name: training
    image: nvcr.io/nvidia/pytorch:21.03-py3
    command: ["mpirun", "--allow-run-as-root"]
    args:
    - "-np"
    - "4"  # 4个进程 (对应4个GPU)
    - "-H"
    - "localhost:4"  # 单节点4个GPU
    - "python"
    - "train.py"
    resources:
      limits:
        nvidia.com/gpu: 4
    env:
    - name: NCCL_IB_DISABLE
      value: "0"  # 启用InfiniBand (如果可用)
    - name: NCCL_SOCKET_IFNAME
      value: "ib0"  # 指定InfiniBand接口
    - name: NCCL_IB_HCA
      value: "mlx5_0,mlx5_1"  # 指定IB设备
    - name: NCCL_DEBUG
      value: "INFO"  # 调试信息
    - name: NCCL_DEBUG_SUBSYS
      value: "INIT,NET"  # 调试网络初始化
  nodeSelector:
    accelerator: nvidia-tesla-v100
```

**NCCL 环境变量配置详解**：

| 变量名 | 默认值 | 说明 |
|-------|-------|------|
| `NCCL_IB_DISABLE` | `0` | 启用(0)/禁用(1)InfiniBand |
| `NCCL_SOCKET_IFNAME` | 自动检测 | 指定网络接口 (ib0, eth0等) |
| `NCCL_IB_HCA` | 自动检测 | 指定IB设备 (mlx5_0等) |
| `NCCL_IB_TIMEOUT` | `22` | IB连接超时 |
| `NCCL_IB_RETRY_CNT` | `7` | IB重试次数 |
| `NCCL_DEBUG` | 空 | 调试级别 (INFO, WARN, TRACE) |
| `NCCL_DEBUG_SUBSYS` | ALL | 调试子系统 (INIT, NET, COLL等) |

### RDMA 与 GPUDirect RDMA

RDMA (Remote Direct Memory Access) 允许网络适配器直接访问内存，无需CPU干预。

#### GPUDirect RDMA 架构

```
CPU Memory ←→ PCIe ←→ GPU Memory
       ↑           ↑
       └─ RDMA ───┘
```

#### 启用 GPUDirect RDMA

```bash
# 在节点上安装
# 方法1: 使用GPU Operator自动配置
helm install gpu-operator nvidia/gpu-operator \
  --set driver.rdma.enabled=true

# 方法2: 手动配置
modprobe nvidia-peermem  # 旧版驱动
# 或使用 DMA-BUF (新版)
```

#### GPUDirect RDMA 性能优势

| 通信路径 | 延迟 | 带宽 | CPU开销 |
|---------|------|------|---------|
| CPU → NIC → CPU | 高 | 中 | 高 |
| GPU → RDMA → GPU | 低 | 高 | 低 |

### InfiniBand 高性能网络

InfiniBand 是专为高性能计算设计的网络协议，提供低延迟和高带宽。

#### InfiniBand 特性

- **低延迟**: <1μs 点对点延迟
- **高带宽**: 200Gbps (HDR), 400Gbps (NDR)
- **RDMA支持**: 零拷贝数据传输
- **拓扑灵活**: Fat-tree, Torus 等

#### MOFED (InfiniBand Drivers)

```bash
# 安装MOFED驱动
wget https://content.mellanox.com/ofed/MLNX_OFED-23.10-1.1.9.0/MLNX_OFED_LINUX-23.10-1.1.9.0-ubuntu20.04-x86_64.tgz
tar -xzf MLNX_OFED_LINUX-23.10-1.1.9.0-ubuntu20.04-x86_64.tgz
cd MLNX_OFED_LINUX-23.10-1.1.9.0-ubuntu20.04-x86_64
./mlnxofedinstall --add-kernel-support

# 重启系统
sudo reboot
```

#### InfiniBand 配置验证

```bash
# 检查IB设备
ibstat
ibv_devices

# 测试带宽
ib_send_bw -d mlx5_0 -i 1

# 测试延迟
ib_send_lat -d mlx5_0 -i 1
```

### GPU 互连技术

#### NVLink 高速互连

NVLink 是 NVIDIA 开发的 GPU 间高速互连技术。

##### NVLink 特性

- **高带宽**: NVLink 3.0 - 每通道50GB/s
- **低延迟**: ~1.5ns 点对点延迟
- **统一内存**: 支持透明的GPU间内存访问
- **多GPU扩展**: 支持8个GPU互联

##### NVLink 拓扑示例

```
GPU0 ── NVLink ── GPU1 ── NVLink ── GPU2 ── NVLink ── GPU3
  │                    │                    │
NVLink             NVLink             NVLink
  │                    │                    │
GPU7 ── NVLink ── GPU6 ── NVLink ── GPU5 ── NVLink ── GPU4
```

#### PCIe 基础互连

PCIe 是 GPU 与主机系统通信的标准接口。

##### PCIe 世代对比

| PCIe 版本 | 带宽 (×16) | 应用场景 |
|----------|-----------|---------|
| PCIe 3.0 | 15.75 GB/s | 入门级GPU |
| PCIe 4.0 | 31.5 GB/s | 主流GPU |
| PCIe 5.0 | 63 GB/s | 高端GPU |
| PCIe 6.0 | 126 GB/s | 未来GPU |

### 网络拓扑优化

#### Fat-Tree 拓扑

Fat-Tree 是数据中心最常用的网络拓扑。

```
        Spine Switches
      /     |     \
     /      |      \
Leaf1 ─── Leaf2 ─── Leaf3
  │        │        │
Node1    Node2    Node3
```

#### 网络配置优化

```bash
# 设置网络参数
echo "net.core.rmem_max=2147483647" >> /etc/sysctl.conf
echo "net.core.wmem_max=2147483647" >> /etc/sysctl.conf
echo "net.ipv4.tcp_rmem=4096 87380 2147483647" >> /etc/sysctl.conf
echo "net.ipv4.tcp_wmem=4096 65536 2147483647" >> /etc/sysctl.conf

# 应用配置
sysctl -p

# 设置中断亲和性
set_irq_affinity.sh
```

#### NCCL 网络优化

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: optimized-nccl-training
spec:
  containers:
  - name: training
    image: nvcr.io/nvidia/pytorch:23.10-py3
    resources:
      limits:
        nvidia.com/gpu: 8
    env:
    - name: NCCL_IB_DISABLE
      value: "0"
    - name: NCCL_SOCKET_IFNAME
      value: "ib0,ib1,ib2,ib3"  # 多端口绑定
    - name: NCCL_IB_HCA
      value: "mlx5_0,mlx5_1,mlx5_2,mlx5_3"
    - name: NCCL_IB_TIMEOUT
      value: "22"
    - name: NCCL_IB_RETRY_CNT
      value: "7"
    - name: NCCL_DEBUG
      value: "WARN"
    - name: NCCL_DEBUG_SUBSYS
      value: "INIT,NET"
```

### 多机多卡分布式训练

#### Horovod + NCCL 示例

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: distributed-training
spec:
  parallelism: 4  # 4个worker (每节点1个)
  completions: 4
  template:
    spec:
      containers:
      - name: training
        image: nvcr.io/nvidia/pytorch:23.10-py3
        command:
        - horovodrun
        - --mpi
        - --host-discovery-script
        - get_hosts.py
        - python
        - train_horovod.py
        resources:
          limits:
            nvidia.com/gpu: 1
        env:
        - name: HOROVOD_MPI_THREADS_DISABLE
          value: "1"
        volumeMounts:
        - name: training-data
          mountPath: /data
      volumes:
      - name: training-data
        persistentVolumeClaim:
          claimName: training-data-pvc
      restartPolicy: OnFailure
```

#### PyTorch Distributed 示例

```python
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

def setup(rank, world_size):
    # 初始化分布式环境
    dist.init_process_group(
        backend='nccl',
        init_method='env://',
        world_size=world_size,
        rank=rank
    )

def cleanup():
    dist.destroy_process_group()

def train(rank, world_size):
    setup(rank, world_size)

    # 创建模型和优化器
    model = torch.nn.Linear(10, 1).cuda(rank)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

    # 训练循环
    for epoch in range(10):
        # 前向传播
        output = model(torch.randn(32, 10).cuda(rank))
        loss = torch.nn.functional.mse_loss(output, torch.randn(32, 1).cuda(rank))

        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # 同步参数
        for param in model.parameters():
            dist.all_reduce(param.grad.data, op=dist.ReduceOp.SUM)
            param.grad.data /= world_size

    cleanup()

if __name__ == '__main__':
    world_size = int(os.environ['WORLD_SIZE'])
    rank = int(os.environ['RANK'])
    mp.spawn(train, args=(world_size,), nprocs=world_size, join=True)
```

#### Kubernetes 多机训练配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: training-config
data:
  train.sh: |
    #!/bin/bash
    export NCCL_IB_DISABLE=0
    export NCCL_SOCKET_IFNAME=ib0
    export NCCL_DEBUG=INFO

    # 获取所有pod的IP地址
    hosts=$(nslookup $MY_POD_NAME.training.svc.cluster.local | grep Address | tail -n +2 | awk '{print $2}')
    host_list=$(echo $hosts | tr ' ' ',')

    mpirun -np $WORLD_SIZE \
           -H $host_list \
           --bind-to none \
           --map-by slot \
           python train.py
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: distributed-training
spec:
  replicas: 4  # 4个节点
  serviceName: training
  selector:
    matchLabels:
      app: distributed-training
  template:
    metadata:
      labels:
        app: distributed-training
    spec:
      containers:
      - name: training
        image: nvcr.io/nvidia/pytorch:23.10-py3
        command: ["/bin/bash", "/config/train.sh"]
        resources:
          limits:
            nvidia.com/gpu: 8  # 每节点8个GPU
        env:
        - name: WORLD_SIZE
          value: "32"  # 4节点 × 8GPU = 32进程
        - name: MY_POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /data
      volumes:
      - name: config
        configMap:
          name: training-config
      - name: data
        persistentVolumeClaim:
          claimName: training-data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Ti
```

### 性能监控与调优

#### NCCL 性能测试

```bash
# 安装NCCL测试工具
git clone https://github.com/NVIDIA/nccl-tests.git
cd nccl-tests
make

# 运行AllReduce测试
./build/all_reduce_perf -b 8 -e 128M -f 2 -g 8

# 查看详细统计
NCCL_DEBUG=INFO ./build/all_reduce_perf -b 8 -e 128M -f 2 -g 8
```

#### 网络性能监控

```bash
# 使用ibstat监控IB状态
ibstat

# 使用perf监控网络性能
perf stat -e ib_mad_send,ib_mad_recv mpirun -np 4 ./app

# 使用sar监控网络流量
sar -n DEV 1
```

#### GPU 通信监控

```bash
# DCGM监控NCCL指标
dcgmi dmon -e 1001,1002,1003  # NCCL相关的指标

# nvidia-smi监控NVLink
nvidia-smi nvlink -s

# NCCL调试信息
export NCCL_DEBUG=INFO
export NCCL_DEBUG_SUBSYS=COLL
```

---

*最后更新时间: 2026年1月4日*
*Kubernetes 版本: v1.27+*
*HAMi 版本: v2.4+*
*Volcano 版本: v1.9+*
*NVIDIA GPU Operator 版本: v25.10.1*
*AMD GPU Operator 版本: v1.0+*
*Intel GPU Plugin 版本: v0.28+*
*NCCL 版本: v2.18+*
*MOFED 版本: v23.10+* 