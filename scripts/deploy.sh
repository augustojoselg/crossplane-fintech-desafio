#!/bin/bash

# =============================================================================
# SCRIPT DE DEPLOY AUTOMATIZADO - PLATAFORMA FINTECH
# =============================================================================
# Este script automatiza o deploy completo da plataforma fintech
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$PROJECT_ROOT/logs/deploy_${TIMESTAMP}.log"

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
# FUNÇÕES DE VERIFICAÇÃO
# =============================================================================
check_prerequisites() {
    log_info "Verificando pré-requisitos..."
    
    # Verificar kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl não está instalado"
        exit 1
    fi
    
    # Verificar helm
    if ! command -v helm &> /dev/null; then
        log_error "helm não está instalado"
        exit 1
    fi
    
    # Verificar crossplane CLI
    if ! command -v kubectl-crossplane &> /dev/null; then
        log_warning "kubectl-crossplane não está instalado - instalando..."
        install_crossplane_cli
    fi
    
    # Verificar AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI não está instalado"
        exit 1
    fi
    
    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker não está instalado"
        exit 1
    fi
    
    log_success "Pré-requisitos verificados com sucesso"
}

check_kubernetes_connection() {
    log_info "Verificando conexão com Kubernetes..."
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Não foi possível conectar ao cluster Kubernetes"
        exit 1
    fi
    
    log_success "Conexão com Kubernetes estabelecida"
}

check_aws_credentials() {
    log_info "Verificando credenciais AWS..."
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "Credenciais AWS não configuradas ou inválidas"
        exit 1
    fi
    
    log_success "Credenciais AWS verificadas"
}

# =============================================================================
# FUNÇÕES DE INSTALAÇÃO
# =============================================================================
install_crossplane_cli() {
    log_info "Instalando Crossplane CLI..."
    
    # Detectar sistema operacional
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    if [[ "$ARCH" == "x86_64" ]]; then
        ARCH="amd64"
    elif [[ "$ARCH" == "aarch64" ]]; then
        ARCH="arm64"
    fi
    
    # Download e instalação
    CROSSPLANE_VERSION="v1.14.0"
    DOWNLOAD_URL="https://releases.crossplane.io/stable/${CROSSPLANE_VERSION}/bin/${OS}/${ARCH}/kubectl-crossplane"
    
    curl -L "$DOWNLOAD_URL" -o /tmp/kubectl-crossplane
    chmod +x /tmp/kubectl-crossplane
    sudo mv /tmp/kubectl-crossplane /usr/local/bin/
    
    log_success "Crossplane CLI instalado com sucesso"
}

# =============================================================================
# FUNÇÕES DE DEPLOY
# =============================================================================
deploy_crossplane() {
    log_info "Deployando Crossplane..."
    
    # Criar namespace
    kubectl create namespace crossplane-system --dry-run=client -o yaml | kubectl apply -f -
    
    # Adicionar repositório Helm
    helm repo add crossplane-stable https://charts.crossplane.io/stable
    helm repo update
    
    # Instalar Crossplane
    helm upgrade --install crossplane crossplane-stable/crossplane \
        --namespace crossplane-system \
        --create-namespace \
        --wait \
        --timeout 10m
    
    # Aguardar Crossplane estar pronto
    log_info "Aguardando Crossplane estar pronto..."
    kubectl wait --for=condition=ready pod -l app=crossplane -n crossplane-system --timeout=300s
    
    log_success "Crossplane deployado com sucesso"
}

deploy_providers() {
    log_info "Deployando providers Crossplane..."
    
    # Deploy do provider AWS
    kubectl apply -f "$PROJECT_ROOT/crossplane/providers/provider-aws.yaml"
    
    # Deploy do provider Helm
    kubectl apply -f "$PROJECT_ROOT/crossplane/providers/provider-helm.yaml"
    
    # Aguardar providers estarem prontos
    log_info "Aguardando providers estarem prontos..."
    kubectl wait --for=condition=healthy provider.pkg.crossplane.io/provider-aws --timeout=300s
    kubectl wait --for=condition=healthy provider.pkg.crossplane.io/provider-helm --timeout=300s
    
    log_success "Providers deployados com sucesso"
}

deploy_xrds() {
    log_info "Deployando XRDs..."
    
    kubectl apply -f "$PROJECT_ROOT/crossplane/xrds/"
    
    log_success "XRDs deployados com sucesso"
}

deploy_compositions() {
    log_info "Deployando compositions..."
    
    kubectl apply -f "$PROJECT_ROOT/crossplane/compositions/"
    
    log_success "Compositions deployadas com sucesso"
}

deploy_platform_instance() {
    log_info "Deployando instância da plataforma..."
    
    # Substituir variáveis no arquivo de instância
    envsubst < "$PROJECT_ROOT/crossplane/instances/fintech-platform-instance.yaml" | kubectl apply -f -
    
    log_success "Instância da plataforma deployada com sucesso"
}

deploy_kubernetes_resources() {
    log_info "Deployando recursos Kubernetes..."
    
    # Namespaces
    kubectl apply -f "$PROJECT_ROOT/k8s/namespaces/"
    
    # Aplicações
    kubectl apply -f "$PROJECT_ROOT/k8s/apps/transaction-api/"
    kubectl apply -f "$PROJECT_ROOT/k8s/apps/notification-service/"
    
    # Monitoring
    kubectl apply -f "$PROJECT_ROOT/k8s/monitoring/"
    
    # Segurança
    kubectl apply -f "$PROJECT_ROOT/k8s/security/"
    
    log_success "Recursos Kubernetes deployados com sucesso"
}

deploy_monitoring() {
    log_info "Deployando stack de monitoring..."
    
    # Prometheus Operator
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --wait \
        --timeout 15m \
        --values "$PROJECT_ROOT/k8s/monitoring/prometheus-values.yaml"
    
    # Grafana dashboards
    kubectl apply -f "$PROJECT_ROOT/k8s/monitoring/grafana-dashboards/"
    
    log_success "Stack de monitoring deployado com sucesso"
}

deploy_ingress_controller() {
    log_info "Deployando NGINX Ingress Controller..."
    
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    
    kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f -
    
    helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --create-namespace \
        --wait \
        --timeout 10m \
        --values "$PROJECT_ROOT/k8s/ingress/nginx-values.yaml"
    
    log_success "NGINX Ingress Controller deployado com sucesso"
}

# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO DE DEPLOY
# =============================================================================
verify_deployment() {
    log_info "Verificando deployment..."
    
    # Verificar Crossplane
    kubectl get pods -n crossplane-system
    
    # Verificar providers
    kubectl get providers.pkg.crossplane.io
    
    # Verificar instância da plataforma
    kubectl get fintechplatforms.platform.fintech.crossplane.io
    
    # Verificar pods das aplicações
    kubectl get pods -n fintech-platform
    kubectl get pods -n monitoring
    
    # Verificar serviços
    kubectl get services -n fintech-platform
    kubectl get services -n monitoring
    
    # Verificar ingress
    kubectl get ingress -n fintech-platform
    
    log_success "Verificação de deployment concluída"
}

# =============================================================================
# FUNÇÕES DE CONFIGURAÇÃO
# =============================================================================
setup_environment() {
    log_info "Configurando ambiente..."
    
    # Carregar variáveis de ambiente
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
    else
        log_warning "Arquivo .env não encontrado, usando valores padrão"
        export AWS_REGION="us-east-1"
        export AWS_ACCOUNT_ID="123456789012"
        export PLATFORM_NAME="fintech-platform"
        export ENVIRONMENT="production"
    fi
    
    # Criar diretório de logs
    mkdir -p "$PROJECT_ROOT/logs"
    
    log_success "Ambiente configurado"
}

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================
main() {
    log_info "Iniciando deploy da plataforma fintech..."
    log_info "Timestamp: $TIMESTAMP"
    log_info "Log file: $LOG_FILE"
    
    # Setup inicial
    setup_environment
    
    # Verificações
    check_prerequisites
    check_kubernetes_connection
    check_aws_credentials
    
    # Deploy em ordem
    deploy_crossplane
    deploy_providers
    deploy_xrds
    deploy_compositions
    deploy_platform_instance
    
    # Aguardar infraestrutura estar pronta
    log_info "Aguardando infraestrutura estar pronta..."
    sleep 60
    
    deploy_ingress_controller
    deploy_monitoring
    deploy_kubernetes_resources
    
    # Verificação final
    verify_deployment
    
    log_success "Deploy da plataforma fintech concluído com sucesso!"
    log_info "Acesse: https://api.fintech.local"
    log_info "Grafana: https://grafana.fintech.local"
    log_info "Logs salvos em: $LOG_FILE"
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
