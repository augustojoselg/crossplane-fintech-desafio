#!/bin/bash

# =============================================================================
# SCRIPT DE TESTE DE INFRAESTRUTURA - PLATAFORMA FINTECH
# =============================================================================
# Este script valida toda a infraestrutura da plataforma fintech
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$PROJECT_ROOT/logs/test_${TIMESTAMP}.log"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# FUNÇÕES DE LOGGING
# =============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# =============================================================================
# FUNÇÕES DE TESTE
# =============================================================================
test_kubernetes_cluster() {
    log_info "Testando cluster Kubernetes..."
    
    # Verificar conexão
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Não foi possível conectar ao cluster Kubernetes"
        return 1
    fi
    
    # Verificar versão
    KUBE_VERSION=$(kubectl version --short --client | cut -d' ' -f3)
    log_info "Versão do Kubernetes: $KUBE_VERSION"
    
    # Verificar nodes
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    log_info "Número de nodes: $NODE_COUNT"
    
    # Verificar se todos os nodes estão prontos
    READY_NODES=$(kubectl get nodes --no-headers | grep -c "Ready")
    if [[ "$READY_NODES" -eq "$NODE_COUNT" ]]; then
        log_success "Todos os nodes estão prontos"
    else
        log_error "Alguns nodes não estão prontos"
        return 1
    fi
    
    log_success "Teste do cluster Kubernetes concluído"
}

test_crossplane() {
    log_info "Testando Crossplane..."
    
    # Verificar namespace
    if ! kubectl get namespace crossplane-system &> /dev/null; then
        log_error "Namespace crossplane-system não encontrado"
        return 1
    fi
    
    # Verificar pods do Crossplane
    CROSSPLANE_PODS=$(kubectl get pods -n crossplane-system --no-headers | wc -l)
    log_info "Número de pods do Crossplane: $CROSSPLANE_PODS"
    
    # Verificar se todos os pods estão prontos
    READY_PODS=$(kubectl get pods -n crossplane-system --no-headers | grep -c "Running")
    if [[ "$READY_PODS" -eq "$CROSSPLANE_PODS" ]]; then
        log_success "Todos os pods do Crossplane estão rodando"
    else
        log_error "Alguns pods do Crossplane não estão rodando"
        kubectl get pods -n crossplane-system
        return 1
    fi
    
    # Verificar providers
    PROVIDER_COUNT=$(kubectl get providers.pkg.crossplane.io --no-headers | wc -l)
    log_info "Número de providers: $PROVIDER_COUNT"
    
    # Verificar se todos os providers estão saudáveis
    HEALTHY_PROVIDERS=$(kubectl get providers.pkg.crossplane.io --no-headers | grep -c "Healthy")
    if [[ "$HEALTHY_PROVIDERS" -eq "$PROVIDER_COUNT" ]]; then
        log_success "Todos os providers estão saudáveis"
    else
        log_error "Alguns providers não estão saudáveis"
        kubectl get providers.pkg.crossplane.io
        return 1
    fi
    
    log_success "Teste do Crossplane concluído"
}

test_platform_instance() {
    log_info "Testando instância da plataforma..."
    
    # Verificar se a instância existe
    if ! kubectl get fintechplatforms.platform.fintech.crossplane.io -n crossplane-system &> /dev/null; then
        log_error "Instância da plataforma não encontrada"
        return 1
    fi
    
    # Verificar status da instância
    INSTANCE_STATUS=$(kubectl get fintechplatforms.platform.fintech.crossplane.io -n crossplane-system -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
    if [[ "$INSTANCE_STATUS" == "True" ]]; then
        log_success "Instância da plataforma está pronta"
    else
        log_error "Instância da plataforma não está pronta"
        kubectl describe fintechplatforms.platform.fintech.crossplane.io -n crossplane-system
        return 1
    fi
    
    log_success "Teste da instância da plataforma concluído"
}

test_aws_resources() {
    log_info "Testando recursos AWS..."
    
    # Verificar VPC
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=fintech-vpc" --query 'Vpcs[0].VpcId' --output text)
    if [[ "$VPC_ID" != "None" ]]; then
        log_success "VPC encontrada: $VPC_ID"
    else
        log_error "VPC não encontrada"
        return 1
    fi
    
    # Verificar subnets
    SUBNET_COUNT=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'length(Subnets)' --output text)
    log_info "Número de subnets: $SUBNET_COUNT"
    
    # Verificar RDS
    RDS_STATUS=$(aws rds describe-db-instances --db-instance-identifier fintech-postgresql --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "None")
    if [[ "$RDS_STATUS" == "available" ]]; then
        log_success "RDS PostgreSQL está disponível"
    else
        log_warning "RDS PostgreSQL não está disponível: $RDS_STATUS"
    fi
    
    # Verificar ElastiCache
    REDIS_STATUS=$(aws elasticache describe-replication-groups --replication-group-id fintech-redis --query 'ReplicationGroups[0].Status' --output text 2>/dev/null || echo "None")
    if [[ "$REDIS_STATUS" == "available" ]]; then
        log_success "ElastiCache Redis está disponível"
    else
        log_warning "ElastiCache Redis não está disponível: $REDIS_STATUS"
    fi
    
    log_success "Teste dos recursos AWS concluído"
}

test_kubernetes_resources() {
    log_info "Testando recursos Kubernetes..."
    
    # Verificar namespaces
    NAMESPACES=("fintech-platform" "monitoring" "security" "ingress-nginx")
    for ns in "${NAMESPACES[@]}"; do
        if kubectl get namespace "$ns" &> /dev/null; then
            log_success "Namespace $ns existe"
        else
            log_error "Namespace $ns não existe"
            return 1
        fi
    done
    
    # Verificar deployments
    DEPLOYMENTS=("transaction-api" "notification-service")
    for deployment in "${DEPLOYMENTS[@]}"; do
        if kubectl get deployment "$deployment" -n fintech-platform &> /dev/null; then
            READY_REPLICAS=$(kubectl get deployment "$deployment" -n fintech-platform -o jsonpath='{.status.readyReplicas}')
            DESIRED_REPLICAS=$(kubectl get deployment "$deployment" -n fintech-platform -o jsonpath='{.spec.replicas}')
            if [[ "$READY_REPLICAS" -eq "$DESIRED_REPLICAS" ]]; then
                log_success "Deployment $deployment está pronto"
            else
                log_error "Deployment $deployment não está pronto ($READY_REPLICAS/$DESIRED_REPLICAS)"
                return 1
            fi
        else
            log_error "Deployment $deployment não encontrado"
            return 1
        fi
    done
    
    # Verificar services
    SERVICES=("transaction-api" "notification-service")
    for service in "${SERVICES[@]}"; do
        if kubectl get service "$service" -n fintech-platform &> /dev/null; then
            log_success "Service $service existe"
        else
            log_error "Service $service não existe"
            return 1
        fi
    done
    
    # Verificar ingress
    if kubectl get ingress -n fintech-platform &> /dev/null; then
        log_success "Ingress existe"
    else
        log_error "Ingress não encontrado"
        return 1
    fi
    
    log_success "Teste dos recursos Kubernetes concluído"
}

test_application_endpoints() {
    log_info "Testando endpoints das aplicações..."
    
    # Port-forward para os serviços
    log_info "Configurando port-forward..."
    
    # Testar Transaction API
    kubectl port-forward -n fintech-platform svc/transaction-api 8080:80 &
    TRANSACTION_PID=$!
    sleep 5
    
    # Testar health check
    if curl -f http://localhost:8080/health &> /dev/null; then
        log_success "Transaction API health check passou"
    else
        log_error "Transaction API health check falhou"
        kill $TRANSACTION_PID 2>/dev/null || true
        return 1
    fi
    
    # Testar métricas
    if curl -f http://localhost:8080/metrics &> /dev/null; then
        log_success "Transaction API metrics endpoint funcionando"
    else
        log_error "Transaction API metrics endpoint falhou"
    fi
    
    # Parar port-forward
    kill $TRANSACTION_PID 2>/dev/null || true
    
    # Testar Notification Service
    kubectl port-forward -n fintech-platform svc/notification-service 8081:80 &
    NOTIFICATION_PID=$!
    sleep 5
    
    # Testar health check
    if curl -f http://localhost:8081/health &> /dev/null; then
        log_success "Notification Service health check passou"
    else
        log_error "Notification Service health check falhou"
        kill $NOTIFICATION_PID 2>/dev/null || true
        return 1
    fi
    
    # Parar port-forward
    kill $NOTIFICATION_PID 2>/dev/null || true
    
    log_success "Teste dos endpoints das aplicações concluído"
}

test_monitoring_stack() {
    log_info "Testando stack de monitoring..."
    
    # Verificar se o namespace monitoring existe
    if ! kubectl get namespace monitoring &> /dev/null; then
        log_warning "Namespace monitoring não encontrado"
        return 0
    fi
    
    # Verificar Prometheus
    if kubectl get pods -n monitoring -l app=prometheus &> /dev/null; then
        PROMETHEUS_PODS=$(kubectl get pods -n monitoring -l app=prometheus --no-headers | wc -l)
        READY_PROMETHEUS=$(kubectl get pods -n monitoring -l app=prometheus --no-headers | grep -c "Running")
        if [[ "$READY_PROMETHEUS" -eq "$PROMETHEUS_PODS" ]]; then
            log_success "Prometheus está rodando"
        else
            log_warning "Prometheus não está totalmente rodando"
        fi
    else
        log_warning "Prometheus não encontrado"
    fi
    
    # Verificar Grafana
    if kubectl get pods -n monitoring -l app=grafana &> /dev/null; then
        GRAFANA_PODS=$(kubectl get pods -n monitoring -l app=grafana --no-headers | wc -l)
        READY_GRAFANA=$(kubectl get pods -n monitoring -l app=grafana --no-headers | grep -c "Running")
        if [[ "$READY_GRAFANA" -eq "$GRAFANA_PODS" ]]; then
            log_success "Grafana está rodando"
        else
            log_warning "Grafana não está totalmente rodando"
        fi
    else
        log_warning "Grafana não encontrado"
    fi
    
    log_success "Teste da stack de monitoring concluído"
}

test_security_configurations() {
    log_info "Testando configurações de segurança..."
    
    # Verificar Pod Security Standards
    PODS_WITH_ROOT=$(kubectl get pods -n fintech-platform -o jsonpath='{.items[?(@.spec.securityContext.runAsNonRoot==false)].metadata.name}')
    if [[ -z "$PODS_WITH_ROOT" ]]; then
        log_success "Todos os pods estão configurados para não rodar como root"
    else
        log_warning "Alguns pods estão rodando como root: $PODS_WITH_ROOT"
    fi
    
    # Verificar Network Policies
    if kubectl get networkpolicies -n fintech-platform &> /dev/null; then
        NP_COUNT=$(kubectl get networkpolicies -n fintech-platform --no-headers | wc -l)
        log_info "Número de Network Policies: $NP_COUNT"
        log_success "Network Policies configurados"
    else
        log_warning "Network Policies não encontrados"
    fi
    
    # Verificar RBAC
    if kubectl get serviceaccounts -n fintech-platform &> /dev/null; then
        SA_COUNT=$(kubectl get serviceaccounts -n fintech-platform --no-headers | wc -l)
        log_info "Número de Service Accounts: $SA_COUNT"
        log_success "RBAC configurado"
    else
        log_warning "Service Accounts não encontrados"
    fi
    
    log_success "Teste das configurações de segurança concluído"
}

test_scaling_configurations() {
    log_info "Testando configurações de escalabilidade..."
    
    # Verificar HPA
    if kubectl get hpa -n fintech-platform &> /dev/null; then
        HPA_COUNT=$(kubectl get hpa -n fintech-platform --no-headers | wc -l)
        log_info "Número de HPAs: $HPA_COUNT"
        
        # Verificar configurações específicas
        for hpa in $(kubectl get hpa -n fintech-platform -o name); do
            MIN_REPLICAS=$(kubectl get "$hpa" -n fintech-platform -o jsonpath='{.spec.minReplicas}')
            MAX_REPLICAS=$(kubectl get "$hpa" -n fintech-platform -o jsonpath='{.spec.maxReplicas}')
            log_info "HPA $hpa: $MIN_REPLICAS - $MAX_REPLICAS réplicas"
        done
        
        log_success "HPA configurado"
    else
        log_warning "HPA não encontrado"
    fi
    
    # Verificar Cluster Autoscaler
    if kubectl get deployment -n kube-system -l app=cluster-autoscaler &> /dev/null; then
        log_success "Cluster Autoscaler configurado"
    else
        log_warning "Cluster Autoscaler não encontrado"
    fi
    
    log_success "Teste das configurações de escalabilidade concluído"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================
main() {
    log_info "Iniciando testes de infraestrutura da plataforma fintech..."
    log_info "Timestamp: $TIMESTAMP"
    log_info "Log file: $LOG_FILE"
    
    # Criar diretório de logs
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Executar testes em sequência
    local tests_passed=0
    local tests_failed=0
    
    # Lista de testes
    local test_functions=(
        "test_kubernetes_cluster"
        "test_crossplane"
        "test_platform_instance"
        "test_aws_resources"
        "test_kubernetes_resources"
        "test_application_endpoints"
        "test_monitoring_stack"
        "test_security_configurations"
        "test_scaling_configurations"
    )
    
    # Executar cada teste
    for test_func in "${test_functions[@]}"; do
        log_info "Executando: $test_func"
        if "$test_func"; then
            log_success "✅ $test_func passou"
            ((tests_passed++))
        else
            log_error "❌ $test_func falhou"
            ((tests_failed++))
        fi
        echo ""
    done
    
    # Resumo dos resultados
    log_info "=========================================="
    log_info "RESUMO DOS TESTES"
    log_info "=========================================="
    log_info "Testes passaram: $tests_passed"
    log_info "Testes falharam: $tests_failed"
    log_info "Total de testes: ${#test_functions[@]}"
    
    if [[ $tests_failed -eq 0 ]]; then
        log_success "🎉 Todos os testes passaram! A infraestrutura está funcionando corretamente."
        exit 0
    else
        log_error "⚠️  $tests_failed teste(s) falharam. Verifique os logs para mais detalhes."
        exit 1
    fi
}

# =============================================================================
# TRATAMENTO DE ERROS
# =============================================================================
trap 'log_error "Erro na linha $LINENO. Comando: $BASH_COMMAND"' ERR

# =============================================================================
# EXECUÇÃO
# =============================================================================
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
