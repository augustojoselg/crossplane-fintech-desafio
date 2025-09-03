# Crossplane Fintech Platform - Desafio Técnico

## Visão Geral

Este projeto implementa uma plataforma fintech completa usando **Crossplane** para gerenciar infraestrutura como código (IaC) na AWS, com dois microserviços containerizados executando em Kubernetes (EKS).

## Arquitetura da Solução

### Infraestrutura AWS via Crossplane
- **VPC** com subnets públicas e privadas (Multi-AZ)
- **Cluster EKS** com node groups otimizados
- **RDS PostgreSQL** Multi-AZ para alta disponibilidade
- **ElastiCache Redis** para cache e sessões
- **Application Load Balancer** para distribuição de tráfego
- **Route53** para DNS e certificados SSL/TLS
- **AWS Secrets Manager** para gerenciamento de credenciais
- **CloudWatch** para observabilidade

### Microserviços
1. **Transaction API Service** (Porta 8080)
   - Implementado em Python com FastAPI
   - Endpoints: POST /transactions, GET /transactions/{id}, GET /health
   - Integração com PostgreSQL e Redis

2. **Notification Service** (Porta 8081)
   - Implementado em Python com FastAPI
   - Endpoints: POST /notify, GET /notifications/{user_id}, GET /health
   - Recebe webhooks do Transaction API

## Características de Nível Sênior

### Crossplane Avançado
- **Compositions customizadas** com dependências complexas
- **XRDs bem estruturados** com validações
- **Provider AWS** configurado com IAM roles de menor privilégio
- **Managed Resources** com dependências corretas

### Kubernetes Enterprise
- **Deployments** com estratégias de rolling update
- **HPA** para escalabilidade automática
- **NetworkPolicies** para isolamento de rede
- **RBAC** com ServiceAccounts apropriados
- **Ingress** com terminação SSL/TLS

### Segurança e Observabilidade
- **Pod Security Standards** para hardening
- **Prometheus + Grafana** para métricas
- **ELK Stack** para logs
- **Distributed tracing** com Jaeger
- **Vulnerability scanning** com Trivy

## Quick Start

### Pré-requisitos
- AWS CLI configurado
- kubectl instalado
- Helm 3.x
- Docker
- Crossplane CLI

### 1. Configuração Inicial
```bash
# Clone o repositório
git clone <seu-repo>
cd crossplane-fintech-desafio

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações AWS
```

### 2. Deploy da Infraestrutura
```bash
# Instale o Crossplane
kubectl create namespace crossplane-system
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm install crossplane crossplane-stable/crossplane --namespace crossplane-system

# Aguarde o Crossplane estar pronto
kubectl wait --for=condition=ready pod -l app=crossplane -n crossplane-system

# Deploy dos providers e configurações
kubectl apply -f crossplane/providers/
kubectl apply -f crossplane/xrds/
kubectl apply -f crossplane/compositions/

# Deploy da instância da plataforma
kubectl apply -f crossplane/instances/
```

### 3. Deploy das Aplicações
```bash
# Crie os namespaces
kubectl apply -f k8s/namespaces/

# Deploy dos microserviços
kubectl apply -f k8s/apps/transaction-api/
kubectl apply -f k8s/apps/notification-service/

# Deploy do monitoring
kubectl apply -f k8s/monitoring/

# Deploy das configurações de segurança
kubectl apply -f k8s/security/
```

### 4. Verificação
```bash
# Verifique o status dos recursos
kubectl get all -n fintech-platform
kubectl get all -n monitoring

# Teste os endpoints
curl https://api.fintech.local/health
curl https://notifications.fintech.local/health
```

## Estrutura do Projeto

```
fintech-platform/
├── crossplane/           # Configurações Crossplane
│   ├── providers/        # Providers AWS e outros
│   ├── compositions/     # Compositions customizadas
│   ├── xrds/            # Composite Resource Definitions
│   └── instances/        # Instâncias da plataforma
├── k8s/                 # Manifests Kubernetes
│   ├── namespaces/      # Namespaces da aplicação
│   ├── apps/            # Microserviços
│   ├── monitoring/      # Prometheus, Grafana, ELK
│   └── security/        # RBAC, NetworkPolicies
├── docker/              # Dockerfiles e builds
├── docs/                # Documentação técnica
├── scripts/             # Automação e utilitários
└── tests/               # Testes de infraestrutura
```

## Configurações Avançadas

### Variáveis de Ambiente
```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Platform Configuration
PLATFORM_NAME=fintech-platform
ENVIRONMENT=production
DOMAIN=fintech.local

# Database Configuration
DB_INSTANCE_CLASS=db.r6g.large
DB_STORAGE_GB=100
REDIS_NODE_TYPE=cache.r6g.large
```

### Personalização de Recursos
Edite os arquivos em `crossplane/compositions/` para ajustar:
- Tamanhos de instâncias
- Configurações de rede
- Políticas de backup
- Configurações de segurança

## Monitoring e Observabilidade

### Dashboards Disponíveis
- **Fintech Overview**: Visão geral da plataforma
- **Transaction Metrics**: Métricas de transações
- **Infrastructure Health**: Saúde da infraestrutura
- **Security Events**: Eventos de segurança

### Alertas Configurados
- CPU/Memória alta (>80%)
- Latência de API alta (>500ms)
- Falhas de transações (>5%)
- Problemas de conectividade de banco

## Testes e Validação

### Testes de Infraestrutura
```bash
# Execute os testes de infraestrutura
./scripts/test-infrastructure.sh

# Testes de carga
./scripts/load-test.sh

# Testes de resiliência
./scripts/chaos-test.sh
```

### Cenários de Troubleshooting
O projeto inclui cenários documentados para:
- Problemas de conectividade com RDS
- Pods em crash loop
- Degradação de performance

## Segurança

### Implementações de Segurança
- **Pod Security Standards** aplicados
- **Network Policies** para isolamento
- **RBAC** com princípio de menor privilégio
- **Secrets** gerenciados via AWS Secrets Manager
- **HTTPS** end-to-end
- **Vulnerability scanning** automático

## Escalabilidade

### HPA Configurado
- **Transaction API**: Escala baseada em CPU e memória
- **Notification Service**: Escala baseada em fila de mensagens
- **Thresholds**: CPU >70%, Memória >80%

### Auto-scaling de Infraestrutura
- **EKS Node Groups**: Escala automática baseada em demanda
- **RDS**: Escala vertical automática
- **Redis**: Escala horizontal com sharding

## Troubleshooting

### Problemas Comuns

#### Crossplane não está funcionando
```bash
kubectl get pods -n crossplane-system
kubectl logs -n crossplane-system -l app=crossplane
```

#### Microserviços não estão respondendo
```bash
kubectl get pods -n fintech-platform
kubectl logs -n fintech-platform -l app=transaction-api
kubectl logs -n fintech-platform -l app=notification-service
```

#### Problemas de banco de dados
```bash
kubectl get rdsinstance -n fintech-platform
kubectl describe rdsinstance -n fintech-platform
```

## Decisões Arquiteturais

### Por que Crossplane?
- **Declarativo**: Infraestrutura como código verdadeiro
- **Multi-cloud**: Facilita migração futura
- **Kubernetes-native**: Integração perfeita com K8s
- **Compositions**: Reutilização e padronização

### Por que FastAPI?
- **Performance**: Alto throughput para APIs financeiras
- **Async**: Suporte nativo a operações assíncronas
- **Documentação**: Auto-documentação da API
- **Validação**: Validação automática de dados

### Por que PostgreSQL + Redis?
- **PostgreSQL**: ACID compliance para transações financeiras
- **Redis**: Cache de alta performance para consultas frequentes
- **Multi-AZ**: Alta disponibilidade na AWS

## Roadmap Futuro

### Próximas Versões
- **GitOps**: Implementação com ArgoCD
- **Service Mesh**: Istio para comunicação entre serviços
- **Chaos Engineering**: Testes de resiliência automatizados
- **Cost Optimization**: Otimizações automáticas de custo AWS

## Suporte

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Consulte a documentação em `docs/`
- Execute os scripts de troubleshooting

## Licença

Este projeto é parte do desafio técnico da ContaSwap.

---

**Desenvolvido para demonstrar expertise em Cloud-Native, Crossplane e Kubernetes**
