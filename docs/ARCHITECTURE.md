# 🏗️ Arquitetura da Plataforma Fintech

## 📋 Visão Geral

Este documento descreve a arquitetura técnica detalhada da plataforma fintech implementada com Crossplane, Kubernetes e AWS. A solução foi projetada seguindo princípios de arquitetura de nível sênior, com foco em escalabilidade, segurança, observabilidade e manutenibilidade.

## 🎯 Princípios Arquiteturais

### 1. **Infraestrutura como Código (IaC)**
- **Crossplane**: Orquestração declarativa de recursos AWS
- **Compositions**: Reutilização e padronização de infraestrutura
- **XRDs**: Definições de recursos customizados com validações

### 2. **Microserviços**
- **Transaction API Service**: Gerenciamento de transações financeiras
- **Notification Service**: Sistema de notificações em tempo real
- **Comunicação assíncrona**: Webhooks e mensageria

### 3. **Cloud-Native**
- **Kubernetes**: Orquestração de containers
- **Multi-AZ**: Alta disponibilidade na AWS
- **Auto-scaling**: Escalabilidade automática baseada em demanda

### 4. **Segurança First**
- **Pod Security Standards**: Hardening de containers
- **Network Policies**: Isolamento de rede
- **RBAC**: Controle de acesso baseado em roles
- **HTTPS end-to-end**: Criptografia em trânsito

## 🏛️ Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET                                │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    ROUTE53                                     │
│              DNS + Certificados SSL/TLS                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│              APPLICATION LOAD BALANCER                          │
│              Distribuição de tráfego                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    EKS CLUSTER                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   PUBLIC SUBNET │  │  PRIVATE SUBNET │  │ DATABASE SUBNET │ │
│  │                 │  │                 │  │                 │ │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │ │
│  │ │INGRESS NGINX│ │  │ │TRANSACTION │ │  │ │   RDS      │ │ │
│  │ │             │ │  │ │   API      │ │  │ │ POSTGRESQL │ │ │
│  │ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │ │
│  │                 │  │ ┌─────────────┐ │  │ ┌─────────────┐ │ │
│  │                 │  │ │NOTIFICATION│ │  │ │   REDIS    │ │ │
│  │                 │  │ │  SERVICE   │ │  │ │  ELASTICACHE│ │ │
│  │                 │  │ └─────────────┘ │  │ └─────────────┘ │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                    MONITORING STACK                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ PROMETHEUS  │  │   GRAFANA   │  │    JAEGER   │            │
│  │             │  │             │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Componentes da Infraestrutura

### 1. **VPC e Networking**

#### Estrutura de Subnets
```
VPC CIDR: 10.0.0.0/16
├── Public Subnets (AZ-a, AZ-b)
│   ├── 10.0.1.0/24 (us-east-1a)
│   └── 10.0.2.0/24 (us-east-1b)
├── Private Subnets (AZ-a, AZ-b)
│   ├── 10.0.10.0/24 (us-east-1a)
│   └── 10.0.11.0/24 (us-east-1b)
└── Database Subnets (AZ-a, AZ-b)
    ├── 10.0.20.0/24 (us-east-1a)
    └── 10.0.21.0/24 (us-east-1b)
```

#### Security Groups
- **ALB Security Group**: Portas 80/443 para internet
- **Application Security Group**: Portas 8080-8081 entre serviços
- **Database Security Group**: Portas 5432 (PostgreSQL) e 6379 (Redis)

### 2. **Cluster EKS**

#### Configurações
- **Versão**: Kubernetes 1.28
- **Node Groups**: t3.medium com auto-scaling (2-10 nós)
- **Multi-AZ**: Distribuição automática entre zonas
- **Encryption**: Secrets criptografados com KMS

#### Node Affinity
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: platform.fintech.crossplane.io/node-type
              operator: In
              values: ["application"]
```

### 3. **Banco de Dados**

#### RDS PostgreSQL
- **Engine**: PostgreSQL 15.4
- **Instance Class**: db.r6g.large
- **Storage**: 100GB GP3 com criptografia
- **Multi-AZ**: Alta disponibilidade
- **Backup**: Retenção de 7 dias
- **Deletion Protection**: Habilitado

#### ElastiCache Redis
- **Engine**: Redis 7.0
- **Node Type**: cache.r6g.large
- **Nodes**: 2 nós com Multi-AZ
- **Failover**: Automático habilitado

### 4. **Load Balancer**

#### Application Load Balancer
- **Type**: Application Load Balancer
- **Scheme**: Internet-facing
- **IP Type**: IPv4
- **Security Groups**: Restritivos
- **Health Checks**: Configurados para endpoints /health

## 🚀 Arquitetura dos Microserviços

### 1. **Transaction API Service**

#### Tecnologias
- **Framework**: FastAPI (Python 3.11)
- **Banco**: PostgreSQL com SQLAlchemy async
- **Cache**: Redis com aioredis
- **Métricas**: Prometheus client
- **Logging**: Structured logging com structlog

#### Endpoints
```
POST /transactions          - Criar transação
GET  /transactions/{id}     - Buscar transação
GET  /transactions/user/{id} - Transações do usuário
GET  /health               - Health check
GET  /metrics              - Métricas Prometheus
```

#### Arquitetura Interna
```
┌─────────────────────────────────────────────────────────────┐
│                    TRANSACTION API                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   FASTAPI   │  │  VALIDATION │  │   CACHE     │        │
│  │             │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│           │                │                │             │
│           ▼                ▼                ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  DATABASE   │  │  WEBHOOK    │  │  METRICS    │        │
│  │  LAYER      │  │  SERVICE    │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

#### Padrões de Design
- **Repository Pattern**: Abstração de acesso a dados
- **Service Layer**: Lógica de negócio isolada
- **Background Tasks**: Processamento assíncrono de webhooks
- **Circuit Breaker**: Resiliência em chamadas externas

### 2. **Notification Service**

#### Tecnologias
- **Framework**: FastAPI (Python 3.11)
- **Banco**: PostgreSQL com schema separado
- **Cache**: Redis para notificações frequentes
- **Métricas**: Prometheus client
- **Tracing**: OpenTelemetry com Jaeger

#### Endpoints
```
POST /notify                    - Criar notificação
GET  /notifications/{user_id}   - Notificações do usuário
GET  /notifications/{user_id}/unread - Não lidas
PUT  /notifications/{id}/read   - Marcar como lida
GET  /health                    - Health check
GET  /metrics                   - Métricas Prometheus
```

#### Fluxo de Notificações
```
Transaction Created
        │
        ▼
   Webhook Call
        │
        ▼
  Notification Service
        │
        ▼
   Save to Database
        │
        ▼
   Cache Update
        │
        ▼
  External Notification
  (Email, SMS, Push)
```

## 🔒 Arquitetura de Segurança

### 1. **Pod Security Standards**

#### Configurações Aplicadas
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containers:
  - securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
      readOnlyRootFilesystem: true
```

### 2. **Network Policies**

#### Isolamento de Rede
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: transaction-api-network-policy
spec:
  podSelector:
    matchLabels:
      app: transaction-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: fintech-platform
      ports:
        - protocol: TCP
          port: 5432  # PostgreSQL
        - protocol: TCP
          port: 6379  # Redis
```

### 3. **RBAC (Role-Based Access Control)**

#### Service Accounts
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: transaction-api-sa
  namespace: fintech-platform
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/TransactionAPIRole
```

#### Roles e Bindings
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: transaction-api-role
  namespace: fintech-platform
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch"]
```

## 📊 Arquitetura de Observabilidade

### 1. **Métricas (Prometheus)**

#### Métricas de Aplicação
- **Transaction Metrics**: Criadas, consultadas, erros
- **API Metrics**: Latência, throughput, status codes
- **Business Metrics**: Transações por segundo, valor médio

#### Métricas de Infraestrutura
- **Kubernetes Metrics**: CPU, memória, pods
- **AWS Metrics**: RDS, ElastiCache, ALB
- **Custom Metrics**: Latência de webhooks, cache hit ratio

### 2. **Logs (ELK Stack)**

#### Estrutura de Logs
```
┌─────────────────────────────────────────────────────────────┐
│                    LOGGING PIPELINE                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   PODS      │  │  FLUENTD    │  │ELASTICSEARCH│        │
│  │             │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│           │                │                │             │
│           ▼                ▼                ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │STRUCTURED   │  │  PARSING    │  │   KIBANA    │        │
│  │   LOGS      │  │             │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

#### Formato de Logs
```json
{
  "timestamp": "2025-01-02T10:30:00Z",
  "level": "INFO",
  "logger": "transaction_api",
  "message": "Transação criada com sucesso",
  "transaction_id": "TXN1704192600abc123",
  "user_id": "user123",
  "amount": 100.50,
  "currency": "BRL",
  "duration_ms": 45,
  "correlation_id": "req-abc-123-def-456"
}
```

### 3. **Tracing (Jaeger)**

#### Distributed Tracing
- **Transaction Flow**: Rastreamento completo de transações
- **Service Dependencies**: Mapeamento de dependências
- **Performance Analysis**: Identificação de gargalos

#### Spans Configurados
```
Transaction Request
├── Database Query
├── Cache Operation
├── Webhook Call
│   ├── HTTP Request
│   ├── Notification Service
│   └── External Notification
└── Response
```

## 🔄 Arquitetura de Escalabilidade

### 1. **Horizontal Pod Autoscaler (HPA)**

#### Configurações de Escala
```yaml
spec:
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

#### Comportamento de Escala
- **Scale Up**: Estabilização de 60s, política agressiva
- **Scale Down**: Estabilização de 300s, política conservadora
- **Custom Metrics**: RPS e latência como gatilhos

### 2. **Auto-scaling de Infraestrutura**

#### EKS Node Groups
- **Cluster Autoscaler**: Escala automática de nós
- **Node Selectors**: Distribuição por tipo de workload
- **Taints e Tolerations**: Isolamento de workloads

#### RDS Auto-scaling
- **Storage**: Escala automática de storage
- **Instance Class**: Escala vertical automática
- **Read Replicas**: Escala horizontal para leitura

## 🧪 Arquitetura de Testes

### 1. **Testes de Infraestrutura**

#### Terratest
```go
func TestFintechPlatform(t *testing.T) {
    terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
        TerraformDir: "../",
        Vars: map[string]interface{}{
            "environment": "test",
            "platform_name": "fintech-test",
        },
    })
    
    defer terraform.Destroy(t, terraformOptions)
    terraform.InitAndApply(t, terraformOptions)
    
    // Validações
    assert.Equal(t, "available", terraform.Output(t, terraformOptions, "rds_status"))
}
```

### 2. **Testes de Carga**

#### K6 Scripts
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'],
        http_req_failed: ['rate<0.01'],
    },
};

export default function() {
    const response = http.post('https://api.fintech.local/transactions', {
        user_id: 'user123',
        amount: 100,
        currency: 'BRL',
        transaction_type: 'credit'
    });
    
    check(response, {
        'status is 201': (r) => r.status === 201,
        'response time < 500ms': (r) => r.timings.duration < 500,
    });
    
    sleep(1);
}
```

### 3. **Testes de Resiliência**

#### Chaos Engineering
- **Pod Kill**: Simulação de falhas de pods
- **Network Partition**: Isolamento de rede
- **Database Failover**: Teste de Multi-AZ

## 🔧 Configurações de Deploy

### 1. **Helm Charts**

#### Valores Customizados
```yaml
# prometheus-values.yaml
prometheus:
  prometheusSpec:
    retention: 15d
    storageSpec:
      volumeClaimTemplate:
        spec:
          resources:
            requests:
              storage: 100Gi

grafana:
  adminPassword: "admin123"
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
        - name: 'fintech'
          orgId: 1
          folder: ''
          type: file
          disableDeletion: false
          editable: true
          options:
            path: /var/lib/grafana/dashboards/fintech
```

### 2. **Kustomize**

#### Overlays de Ambiente
```
kustomization/
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── overlays/
│   ├── development/
│   │   ├── kustomization.yaml
│   │   └── patches/
│   ├── staging/
│   │   ├── kustomization.yaml
│   │   └── patches/
│   └── production/
│       ├── kustomization.yaml
│       └── patches/
```

## 🚨 Considerações de Troubleshooting

### 1. **Problemas de Conectividade**

#### Database Connection Issues
```bash
# Verificar status do RDS
kubectl get rdsinstance -n fintech-platform
kubectl describe rdsinstance -n fintech-platform

# Verificar security groups
aws ec2 describe-security-groups --group-ids sg-12345678

# Testar conectividade
kubectl run test-db --rm -it --image=postgres:15 -- psql -h fintech-postgresql -U admin -d fintech_db
```

#### Redis Connection Issues
```bash
# Verificar status do ElastiCache
kubectl get replicationgroup -n fintech-platform
kubectl describe replicationgroup -n fintech-platform

# Testar conectividade
kubectl run test-redis --rm -it --image=redis:7 -- redis-cli -h fintech-redis -p 6379 ping
```

### 2. **Pod Crash Loop**

#### Análise de Logs
```bash
# Logs do pod
kubectl logs -n fintech-platform -l app=transaction-api --tail=100

# Descrição do pod
kubectl describe pod -n fintech-platform -l app=transaction-api

# Eventos do namespace
kubectl get events -n fintech-platform --sort-by='.lastTimestamp'
```

#### Debugging de Configurações
```bash
# Verificar ConfigMaps
kubectl get configmaps -n fintech-platform
kubectl describe configmap transaction-api-config -n fintech-platform

# Verificar Secrets
kubectl get secrets -n fintech-platform
kubectl describe secret transaction-api-secrets -n fintech-platform
```

### 3. **Performance Issues**

#### Análise de Métricas
```bash
# Port-forward para Prometheus
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090

# Port-forward para Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

#### Análise de Recursos
```bash
# Top de pods
kubectl top pods -n fintech-platform

# Descrição de nodes
kubectl describe nodes

# Métricas de HPA
kubectl describe hpa transaction-api-hpa -n fintech-platform
```

## 🔮 Roadmap e Melhorias Futuras

### 1. **GitOps com ArgoCD**
- **Declarative Deployments**: Configurações versionadas
- **Automated Sync**: Sincronização automática com Git
- **Rollback Automation**: Rollback automático em falhas

### 2. **Service Mesh com Istio**
- **Traffic Management**: Roteamento avançado de tráfego
- **Security**: mTLS e políticas de segurança
- **Observability**: Métricas, logs e tracing unificados

### 3. **Chaos Engineering**
- **Automated Testing**: Testes de resiliência automatizados
- **Failure Injection**: Simulação controlada de falhas
- **Recovery Validation**: Validação de procedimentos de recuperação

### 4. **Cost Optimization**
- **Spot Instances**: Uso de instâncias spot para workloads não críticos
- **Right-sizing**: Otimização automática de recursos
- **Scheduling Optimization**: Otimização de agendamento de pods

## 📚 Referências e Recursos

### 1. **Documentação Oficial**
- [Crossplane Documentation](https://crossplane.io/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [AWS EKS Documentation](https://docs.aws.amazon.com/eks/)

### 2. **Best Practices**
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [12-Factor App Methodology](https://12factor.net/)

### 3. **Ferramentas e Utilitários**
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)
- [Jaeger](https://www.jaegertracing.io/)
- [K6](https://k6.io/)
- [Terratest](https://terratest.gruntwork.io/)

---

**Esta arquitetura representa uma implementação de nível sênior, demonstrando expertise em Cloud-Native, Crossplane, Kubernetes e práticas de DevOps modernas.**
