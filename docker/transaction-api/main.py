# =============================================================================
# TRANSACTION API SERVICE - MAIN APPLICATION
# =============================================================================
# Microserviço para gerenciamento de transações financeiras
# =============================================================================

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import structlog

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# =============================================================================
# CONFIGURAÇÃO DO FASTAPI
# =============================================================================
app = FastAPI(
    title="Transaction API Service",
    description="API para gerenciamento de transações financeiras",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# =============================================================================
# MIDDLEWARES
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# =============================================================================
# MÉTRICAS PROMETHEUS
# =============================================================================
# Contadores para métricas de negócio
TRANSACTION_CREATED = Counter('transactions_created_total', 'Total de transações criadas')
TRANSACTION_RETRIEVED = Counter('transactions_retrieved_total', 'Total de transações consultadas')
TRANSACTION_ERRORS = Counter('transaction_errors_total', 'Total de erros nas transações')

# Histogramas para latência
TRANSACTION_DURATION = Histogram('transaction_duration_seconds', 'Duração das operações de transação')
API_REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Duração das requisições da API')

# =============================================================================
# MODELOS DE DADOS
# =============================================================================
Base = declarative_base()

class TransactionDB(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(String(50), index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    transaction_type = Column(String(20), nullable=False)  # credit, debit, transfer
    status = Column(String(20), nullable=False, default="pending")  # pending, completed, failed
    description = Column(Text)
    metadata = Column(Text)  # JSON string
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

class TransactionCreate(BaseModel):
    user_id: str = Field(..., description="ID do usuário")
    amount: float = Field(..., gt=0, description="Valor da transação")
    currency: str = Field(default="BRL", max_length=3, description="Moeda da transação")
    transaction_type: str = Field(..., description="Tipo da transação")
    description: Optional[str] = Field(None, description="Descrição da transação")
    metadata: Optional[Dict] = Field(None, description="Metadados adicionais")
    
    @validator('transaction_type')
    def validate_transaction_type(cls, v):
        allowed_types = ['credit', 'debit', 'transfer']
        if v not in allowed_types:
            raise ValueError(f'transaction_type deve ser um dos seguintes: {allowed_types}')
        return v
    
    @validator('currency')
    def validate_currency(cls, v):
        if len(v) != 3:
            raise ValueError('currency deve ter exatamente 3 caracteres')
        return v.upper()

class TransactionResponse(BaseModel):
    id: int
    transaction_id: str
    user_id: str
    amount: float
    currency: str
    transaction_type: str
    status: str
    description: Optional[str]
    metadata: Optional[Dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    database: str
    redis: str
    uptime: float

# =============================================================================
# CONFIGURAÇÃO DE BANCO E CACHE
# =============================================================================
# Configurações (em produção, usar variáveis de ambiente)
DATABASE_URL = "postgresql+asyncpg://admin:password@fintech-postgresql:5432/fintech_db"
REDIS_URL = "redis://fintech-redis:6379"
NOTIFICATION_SERVICE_URL = "http://notification-service:8081/notify"

# Engine do banco de dados
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Cliente Redis
redis_client: Optional[redis.Redis] = None

# =============================================================================
# DEPENDÊNCIAS
# =============================================================================
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_redis() -> redis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def generate_transaction_id() -> str:
    """Gera um ID único para transação"""
    timestamp = int(time.time() * 1000)
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return f"TXN{timestamp}{unique_id}"

async def send_notification(transaction_data: dict):
    """Envia notificação para o serviço de notificações"""
    try:
        async with httpx.AsyncClient() as client:
            notification_payload = {
                "user_id": transaction_data["user_id"],
                "type": "transaction_created",
                "title": "Nova Transação",
                "message": f"Transação de {transaction_data['amount']} {transaction_data['currency']} foi criada",
                "metadata": transaction_data
            }
            
            response = await client.post(
                NOTIFICATION_SERVICE_URL,
                json=notification_payload,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info("Notificação enviada com sucesso", transaction_id=transaction_data["transaction_id"])
            else:
                logger.warning("Falha ao enviar notificação", status_code=response.status_code)
                
    except Exception as e:
        logger.error("Erro ao enviar notificação", error=str(e), transaction_id=transaction_data["transaction_id"])

# =============================================================================
# ENDPOINTS DA API
# =============================================================================
@app.get("/", response_model=Dict[str, str])
async def root():
    """Endpoint raiz da API"""
    return {
        "message": "Transaction API Service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Endpoint de verificação de saúde da aplicação"""
    start_time = time.time()
    
    # Verificar banco de dados
    db_status = "healthy"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Verificar Redis
    redis_status = "healthy"
    try:
        redis_client = await get_redis()
        await redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    # Calcular uptime (em produção, usar variável global)
    uptime = time.time() - start_time
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        database=db_status,
        redis=redis_status,
        uptime=uptime
    )

@app.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction: TransactionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Cria uma nova transação financeira"""
    start_time = time.time()
    
    try:
        # Gerar ID único para transação
        transaction_id = generate_transaction_id()
        
        # Criar objeto de transação para banco
        db_transaction = TransactionDB(
            transaction_id=transaction_id,
            user_id=transaction.user_id,
            amount=transaction.amount,
            currency=transaction.currency,
            transaction_type=transaction.transaction_type,
            description=transaction.description,
            metadata=str(transaction.metadata) if transaction.metadata else None,
            status="pending"
        )
        
        # Salvar no banco
        db.add(db_transaction)
        await db.commit()
        await db.refresh(db_transaction)
        
        # Cache da transação
        cache_key = f"transaction:{transaction_id}"
        await redis_client.setex(
            cache_key,
            3600,  # TTL de 1 hora
            str(db_transaction.__dict__)
        )
        
        # Métricas
        TRANSACTION_CREATED.inc()
        TRANSACTION_DURATION.observe(time.time() - start_time)
        
        # Log da transação
        logger.info(
            "Transação criada com sucesso",
            transaction_id=transaction_id,
            user_id=transaction.user_id,
            amount=transaction.amount,
            currency=transaction.currency
        )
        
        # Enviar notificação em background
        background_tasks.add_task(
            send_notification,
            {
                "transaction_id": transaction_id,
                "user_id": transaction.user_id,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "transaction_type": transaction.transaction_type
            }
        )
        
        return TransactionResponse.from_orm(db_transaction)
        
    except Exception as e:
        TRANSACTION_ERRORS.inc()
        logger.error("Erro ao criar transação", error=str(e), user_id=transaction.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar transação"
        )

@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Busca uma transação específica por ID"""
    start_time = time.time()
    
    try:
        # Tentar buscar do cache primeiro
        cache_key = f"transaction:{transaction_id}"
        cached_transaction = await redis_client.get(cache_key)
        
        if cached_transaction:
            # TODO: Implementar deserialização do cache
            logger.info("Transação encontrada no cache", transaction_id=transaction_id)
        
        # Buscar do banco
        result = await db.execute(
            "SELECT * FROM transactions WHERE transaction_id = :transaction_id AND is_active = true",
            {"transaction_id": transaction_id}
        )
        transaction_data = result.fetchone()
        
        if not transaction_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transação não encontrada"
            )
        
        # Métricas
        TRANSACTION_RETRIEVED.inc()
        TRANSACTION_DURATION.observe(time.time() - start_time)
        
        # Log da consulta
        logger.info("Transação consultada com sucesso", transaction_id=transaction_id)
        
        # TODO: Implementar conversão para TransactionResponse
        return TransactionResponse(
            id=transaction_data.id,
            transaction_id=transaction_data.transaction_id,
            user_id=transaction_data.user_id,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            transaction_type=transaction_data.transaction_type,
            status=transaction_data.status,
            description=transaction_data.description,
            metadata=eval(transaction_data.metadata) if transaction_data.metadata else None,
            created_at=transaction_data.created_at,
            updated_at=transaction_data.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        TRANSACTION_ERRORS.inc()
        logger.error("Erro ao buscar transação", error=str(e), transaction_id=transaction_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar transação"
        )

@app.get("/transactions/user/{user_id}", response_model=List[TransactionResponse])
async def get_user_transactions(
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Busca todas as transações de um usuário específico"""
    try:
        result = await db.execute(
            """
            SELECT * FROM transactions 
            WHERE user_id = :user_id AND is_active = true 
            ORDER BY created_at DESC 
            LIMIT :limit OFFSET :offset
            """,
            {"user_id": user_id, "limit": limit, "offset": offset}
        )
        
        transactions = result.fetchall()
        
        logger.info("Transações do usuário consultadas", user_id=user_id, count=len(transactions))
        
        # TODO: Implementar conversão para lista de TransactionResponse
        return []
        
    except Exception as e:
        logger.error("Erro ao buscar transações do usuário", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar transações"
        )

@app.get("/metrics")
async def metrics():
    """Endpoint para métricas Prometheus"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# =============================================================================
# EVENTOS DE INICIALIZAÇÃO E FINALIZAÇÃO
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """Evento executado na inicialização da aplicação"""
    logger.info("Transaction API Service iniciando...")
    
    # Criar tabelas se não existirem
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Transaction API Service iniciado com sucesso")

@app.on_event("shutdown")
async def shutdown_event():
    """Evento executado na finalização da aplicação"""
    logger.info("Transaction API Service finalizando...")
    
    # Fechar conexões
    if redis_client:
        await redis_client.close()
    
    await engine.dispose()
    
    logger.info("Transaction API Service finalizado")

# =============================================================================
# MIDDLEWARE DE LOGGING
# =============================================================================
@app.middleware("http")
async def log_requests(request, call_next):
    """Middleware para logging de requisições"""
    start_time = time.time()
    
    # Processar requisição
    response = await call_next(request)
    
    # Calcular duração
    duration = time.time() - start_time
    API_REQUEST_DURATION.observe(duration)
    
    # Log da requisição
    logger.info(
        "Requisição processada",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration=duration
    )
    
    return response

# =============================================================================
# EXECUÇÃO DIRETA (DESENVOLVIMENTO)
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
