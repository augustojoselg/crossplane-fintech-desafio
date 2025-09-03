# 🚨 Guia de Troubleshooting - Plataforma Fintech

## 📋 Visão Geral

Este documento fornece um guia completo de troubleshooting para a plataforma fintech, incluindo cenários comuns, análise de problemas, soluções e prevenção. Cada cenário inclui análise detalhada, comandos de diagnóstico e soluções passo a passo.

## 🎯 Cenários de Troubleshooting

### 1. **Problemas de Conectividade com RDS PostgreSQL**

#### 🚨 Cenário
O Transaction API Service não consegue conectar ao banco de dados RDS PostgreSQL, retornando erros de conexão e causando falhas nas transações.

#### 🔍 Análise do Problema

##### 1.1 Verificação de Status dos Recursos
```bash
# Verificar status da instância RDS
kubectl get rdsinstance -n fintech-platform
kubectl describe rdsinstance -n fintech-platform

# Verificar status dos pods
kubectl get pods -n fintech-platform -l app=transaction-api
kubectl describe pod -n fintech-platform -l app=transaction-api

# Verificar logs da aplicação
kubectl logs -n fintech-platform -l app=transaction-api --tail=100
```

##### 1.2 Verificação de Conectividade de Rede
```bash
# Verificar security groups
aws ec2 describe-security-groups --group-ids sg-12345678

# Verificar subnets
aws ec2 describe-subnets --subnet-ids subnet-12345678

# Verificar route tables
aws ec2 describe-route-tables --route-table-ids rtb-12345678

# Testar conectividade do pod para o RDS
kubectl run test-db --rm -it --image=postgres:15 -- psql -h fintech-postgresql -U admin -d fintech_db
```

##### 1.3 Verificação de Configurações
```bash
# Verificar secrets
kubectl get secrets -n fintech-platform
kubectl describe secret transaction-api-secrets -n fintech-platform

# Verificar ConfigMaps
kubectl get configmaps -n fintech-platform
kubectl describe configmap transaction-api-config -n fintech-platform

# Verificar variáveis de ambiente
kubectl exec -n fintech-platform -l app=transaction-api -- env | grep DATABASE
```

#### 🛠️ Soluções

##### Solução 1: Security Groups Incorretos
```bash
# Identificar security group do RDS
RDS_SG=$(aws rds describe-db-instances --db-instance-identifier fintech-postgresql --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text)

# Verificar regras de entrada
aws ec2 describe-security-group-rules --filters Name=group-id,Values=$RDS_SG

# Adicionar regra para permitir tráfego do security group da aplicação
APP_SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=fintech-app-sg --query 'SecurityGroups[0].GroupId' --output text)

aws ec2 authorize-security-group-ingress \
    --group-id $RDS_SG \
    --protocol tcp \
    --port 5432 \
    --source-group $APP_SG
```

##### Solução 2: DNS Resolution
```bash
# Verificar resolução DNS no pod
kubectl exec -n fintech-platform -l app=transaction-api -- nslookup fintech-postgresql

# Verificar configuração do RDS
aws rds describe-db-instances --db-instance-identifier fintech-postgresql --query 'DBInstances[0].Endpoint'

# Verificar se o endpoint está correto no secret
kubectl get secret transaction-api-secrets -n fintech-platform -o jsonpath='{.data.database-url}' | base64 -d
```

##### Solução 3: Connection Pooling
```bash
# Verificar configurações de pool no código
kubectl exec -n fintech-platform -l app=transaction-api -- cat /app/config/database.py

# Ajustar configurações de pool
kubectl patch configmap transaction-api-config -n fintech-platform --patch '{"data":{"DB_POOL_SIZE":"10","DB_MAX_OVERFLOW":"20"}}'

# Reiniciar deployment
kubectl rollout restart deployment/transaction-api -n fintech-platform
```

#### 🔒 Prevenção

##### 1.1 Monitoramento Proativo
```yaml
# Prometheus alert rule
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: database-connection-alert
  namespace: monitoring
spec:
  groups:
    - name: database
      rules:
        - alert: DatabaseConnectionFailed
          expr: up{job="transaction-api"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "Database connection failed"
            description: "Transaction API cannot connect to database"
```

##### 1.2 Health Checks Robustos
```yaml
# Liveness probe melhorado
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
  successThreshold: 1
```

##### 1.3 Circuit Breaker
```python
# Implementação de circuit breaker
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=30)
async def database_operation():
    # Operação de banco
    pass
```

---

### 2. **Pod Crash Loop**

#### 🚨 Cenário
Um dos pods do Transaction API Service está entrando em crash loop, reiniciando continuamente e causando indisponibilidade do serviço.

#### 🔍 Análise do Problema

##### 2.1 Análise de Logs
```bash
# Verificar status dos pods
kubectl get pods -n fintech-platform -l app=transaction-api

# Verificar eventos do namespace
kubectl get events -n fintech-platform --sort-by='.lastTimestamp'

# Verificar logs do pod em crash
kubectl logs -n fintech-platform -l app=transaction-api --previous --tail=100

# Verificar descrição do pod
kubectl describe pod -n fintech-platform -l app=transaction-api
```

##### 2.2 Análise de Recursos
```bash
# Verificar uso de recursos
kubectl top pods -n fintech-platform

# Verificar descrição dos nodes
kubectl describe nodes

# Verificar quotas e limits
kubectl describe resourcequota -n fintech-platform
kubectl describe limitrange -n fintech-platform
```

##### 2.3 Análise de Configurações
```bash
# Verificar ConfigMaps
kubectl get configmaps -n fintech-platform
kubectl describe configmap transaction-api-config -n fintech-platform

# Verificar Secrets
kubectl get secrets -n fintech-platform
kubectl describe secret transaction-api-secrets -n fintech-platform

# Verificar deployment
kubectl describe deployment transaction-api -n fintech-platform
```

#### 🛠️ Soluções

##### Solução 1: Falta de Recursos
```bash
# Verificar se há recursos disponíveis
kubectl describe nodes | grep -A 10 "Allocated resources"

# Ajustar requests e limits
kubectl patch deployment transaction-api -n fintech-platform --patch '{"spec":{"template":{"spec":{"containers":[{"name":"transaction-api","resources":{"requests":{"cpu":"100m","memory":"256Mi"},"limits":{"cpu":"500m","memory":"512Mi"}}}]}}}}'

# Verificar se o pod consegue ser agendado
kubectl get pods -n fintech-platform -l app=transaction-api -o wide
```

##### Solução 2: Configuração Incorreta
```bash
# Verificar se as variáveis de ambiente estão corretas
kubectl exec -n fintech-platform -l app=transaction-api -- env | sort

# Corrigir ConfigMap
kubectl patch configmap transaction-api-config -n fintech-platform --patch '{"data":{"LOG_LEVEL":"INFO","ENVIRONMENT":"production"}}'

# Reiniciar deployment
kubectl rollout restart deployment/transaction-api -n fintech-platform
```

##### Solução 3: Problema de Imagem
```bash
# Verificar se a imagem existe
docker pull fintech/transaction-api:latest

# Verificar se há problemas na imagem
kubectl run test-image --rm -it --image=fintech/transaction-api:latest -- /bin/bash

# Fazer rollback para versão anterior
kubectl rollout undo deployment/transaction-api -n fintech-platform
```

#### 🔒 Prevenção

##### 2.1 Startup Probes
```yaml
startupProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 30
  successThreshold: 1
```

##### 2.2 Resource Quotas
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: fintech-platform-quota
  namespace: fintech-platform
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
```

##### 2.3 Pod Disruption Budget
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: transaction-api-pdb
  namespace: fintech-platform
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: transaction-api
```

---

### 3. **Degradação de Performance**

#### 🚨 Cenário
A plataforma está experimentando alta latência, timeouts e degradação geral de performance, afetando a experiência do usuário e causando falhas nas transações.

#### 🔍 Análise do Problema

##### 3.1 Análise de Métricas
```bash
# Port-forward para Prometheus
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090

# Port-forward para Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Verificar métricas de latência
curl "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(api_request_duration_seconds_bucket[5m]))"

# Verificar throughput
curl "http://localhost:9090/api/v1/query?query=rate(transactions_created_total[5m])"
```

##### 3.2 Análise de Recursos
```bash
# Verificar uso de CPU e memória
kubectl top pods -n fintech-platform
kubectl top nodes

# Verificar descrição dos nodes
kubectl describe nodes

# Verificar HPA
kubectl describe hpa transaction-api-hpa -n fintech-platform
```

##### 3.3 Análise de Rede
```bash
# Verificar latência de rede
kubectl exec -n fintech-platform -l app=transaction-api -- ping -c 5 fintech-postgresql
kubectl exec -n fintech-platform -l app=transaction-api -- ping -c 5 fintech-redis

# Verificar throughput de rede
kubectl exec -n fintech-platform -l app=transaction-api -- iperf3 -c fintech-postgresql -p 5201
```

#### 🛠️ Soluções

##### Solução 1: Escalabilidade Automática
```bash
# Verificar configurações do HPA
kubectl get hpa transaction-api-hpa -n fintech-platform -o yaml

# Ajustar thresholds do HPA
kubectl patch hpa transaction-api-hpa -n fintech-platform --patch '{"spec":{"metrics":[{"type":"Resource","resource":{"name":"cpu","target":{"type":"Utilization","averageUtilization":50}}}]}}'

# Verificar se o HPA está funcionando
kubectl describe hpa transaction-api-hpa -n fintech-platform
```

##### Solução 2: Otimização de Cache
```bash
# Verificar hit ratio do Redis
kubectl exec -n fintech-platform -l app=transaction-api -- redis-cli -h fintech-redis info stats | grep keyspace

# Ajustar TTL do cache
kubectl patch configmap transaction-api-config -n fintech-platform --patch '{"data":{"REDIS_TTL":"7200"}}'

# Verificar configurações de pool do Redis
kubectl exec -n fintech-platform -l app=transaction-api -- redis-cli -h fintech-redis config get maxclients
```

##### Solução 3: Otimização de Banco
```bash
# Verificar queries lentas
kubectl exec -n fintech-platform -l app=transaction-api -- psql -h fintech-postgresql -U admin -d fintech_db -c "SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Verificar índices
kubectl exec -n fintech-platform -l app=transaction-api -- psql -h fintech-postgresql -U admin -d fintech_db -c "SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch FROM pg_stat_user_indexes ORDER BY idx_scan DESC;"

# Criar índices otimizados
kubectl exec -n fintech-platform -l app=transaction-api -- psql -h fintech-postgresql -U admin -d fintech_db -c "CREATE INDEX CONCURRENTLY idx_transactions_user_id_created_at ON transactions(user_id, created_at);"
```

#### 🔒 Prevenção

##### 3.1 Alertas de Performance
```yaml
# Prometheus alert rule
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: performance-alerts
  namespace: monitoring
spec:
  groups:
    - name: performance
      rules:
        - alert: HighLatency
          expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 0.5
          for: 2m
          labels:
            severity: warning
          annotations:
            summary: "High API latency detected"
            description: "95th percentile latency is above 500ms"
```

##### 3.2 SLOs e SLIs
```yaml
# Service Level Objectives
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: slo-rules
  namespace: monitoring
spec:
  groups:
    - name: slo
      rules:
        - record: slo:request_duration:p95
          expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))
        
        - record: slo:error_rate
          expr: rate(transaction_errors_total[5m]) / rate(transactions_created_total[5m])
```

##### 3.3 Load Testing Automatizado
```yaml
# CronJob para testes de carga
apiVersion: batch/v1
kind: CronJob
metadata:
  name: load-test
  namespace: fintech-platform
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: k6
              image: grafana/k6:latest
              command: ["k6", "run", "/scripts/load-test.js"]
              volumeMounts:
                - name: scripts
                  mountPath: /scripts
          volumes:
            - name: scripts
              configMap:
                name: load-test-scripts
          restartPolicy: Never
```

---

## 🛠️ Ferramentas de Diagnóstico

### 1. **Kubernetes Debugging**

#### Debug Pods
```bash
# Executar debug container
kubectl run debug-pod --rm -it --image=busybox --restart=Never -- sh

# Executar debug no pod existente
kubectl exec -it -n fintech-platform -l app=transaction-api -- /bin/bash

# Port-forward para serviços
kubectl port-forward -n fintech-platform svc/transaction-api 8080:80
```

#### Debug Networking
```bash
# Verificar DNS
kubectl run test-dns --rm -it --image=busybox -- nslookup transaction-api

# Verificar conectividade
kubectl run test-connectivity --rm -it --image=busybox -- wget -O- http://transaction-api:80/health

# Verificar network policies
kubectl get networkpolicies -n fintech-platform
kubectl describe networkpolicy transaction-api-network-policy -n fintech-platform
```

### 2. **AWS Debugging**

#### Debug RDS
```bash
# Verificar status da instância
aws rds describe-db-instances --db-instance-identifier fintech-postgresql

# Verificar eventos
aws rds describe-db-instances --db-instance-identifier fintech-postgresql --query 'DBInstances[0].PendingModifiedValues'

# Verificar logs
aws rds describe-db-log-files --db-instance-identifier fintech-postgresql
```

#### Debug ElastiCache
```bash
# Verificar status do cluster
aws elasticache describe-replication-groups --replication-group-id fintech-redis

# Verificar eventos
aws elasticache describe-events --source-identifier fintech-redis --source-type replication-group
```

### 3. **Application Debugging**

#### Debug FastAPI
```bash
# Verificar logs da aplicação
kubectl logs -n fintech-platform -l app=transaction-api --tail=100 -f

# Verificar métricas da aplicação
kubectl exec -n fintech-platform -l app=transaction-api -- curl localhost:8080/metrics

# Verificar health check
kubectl exec -n fintech-platform -l app=transaction-api -- curl localhost:8080/health
```

#### Debug Database
```bash
# Conectar ao PostgreSQL
kubectl exec -it -n fintech-platform -l app=transaction-api -- psql -h fintech-postgresql -U admin -d fintech_db

# Verificar conexões ativas
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Verificar locks
SELECT * FROM pg_locks WHERE NOT granted;
```

---

## 📊 Dashboards de Troubleshooting

### 1. **Grafana Dashboards**

#### Dashboard de Infraestrutura
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: infrastructure-dashboard
  namespace: monitoring
data:
  dashboard.json: |
    {
      "dashboard": {
        "title": "Infrastructure Overview",
        "panels": [
          {
            "title": "Pod Status",
            "type": "stat",
            "targets": [
              {
                "expr": "count(kube_pod_status_phase{namespace=\"fintech-platform\"}) by (phase)"
              }
            ]
          },
          {
            "title": "Resource Usage",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(container_cpu_usage_seconds_total{namespace=\"fintech-platform\"}[5m])"
              }
            ]
          }
        ]
      }
    }
```

#### Dashboard de Aplicação
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: application-dashboard
  namespace: monitoring
data:
  dashboard.json: |
    {
      "dashboard": {
        "title": "Application Metrics",
        "panels": [
          {
            "title": "Transaction Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "rate(transactions_created_total[5m])"
              }
            ]
          },
          {
            "title": "API Latency",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))"
              }
            ]
          }
        ]
      }
    }
```

---

## 🚀 Procedimentos de Recuperação

### 1. **Recuperação de Falha Total**

#### Procedimento de DR
```bash
# 1. Verificar status de todos os recursos
kubectl get all -A
kubectl get fintechplatforms.platform.fintech.crossplane.io -A

# 2. Verificar status da infraestrutura AWS
aws ec2 describe-instances --filters "Name=tag:Platform,Values=fintech"
aws rds describe-db-instances --db-instance-identifier fintech-postgresql

# 3. Restaurar de backup se necessário
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier fintech-postgresql-restored \
    --db-snapshot-identifier fintech-postgresql-snapshot

# 4. Reaplicar configurações
kubectl apply -f crossplane/instances/
kubectl apply -f k8s/
```

### 2. **Rollback de Deployment**

#### Procedimento de Rollback
```bash
# 1. Verificar histórico de deployments
kubectl rollout history deployment/transaction-api -n fintech-platform

# 2. Fazer rollback para versão anterior
kubectl rollout undo deployment/transaction-api -n fintech-platform

# 3. Verificar status do rollback
kubectl rollout status deployment/transaction-api -n fintech-platform

# 4. Verificar se o serviço está funcionando
kubectl get pods -n fintech-platform -l app=transaction-api
kubectl logs -n fintech-platform -l app=transaction-api --tail=50
```

---

## 📚 Recursos Adicionais

### 1. **Documentação de Referência**
- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [AWS Troubleshooting](https://docs.aws.amazon.com/troubleshooting/)
- [Crossplane Troubleshooting](https://crossplane.io/docs/v1.14/concepts/troubleshooting.html)

### 2. **Ferramentas Recomendadas**
- **k9s**: Interface TUI para Kubernetes
- **Lens**: IDE para Kubernetes
- **kubectx**: Alternância entre contextos
- **kubens**: Alternância entre namespaces

### 3. **Comunidade e Suporte**
- [Kubernetes Slack](https://slack.k8s.io/)
- [Crossplane Community](https://crossplane.io/community/)
- [AWS Developer Forums](https://forums.aws.amazon.com/)

---

**Este guia de troubleshooting representa uma abordagem profissional e sistemática para resolução de problemas em ambientes de produção, demonstrando expertise em operações de plataforma e resolução de incidentes.**
