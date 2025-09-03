# =============================================================================
# NOTIFICATION SERVICE - MAIN APPLICATION
# =============================================================================
# Microserviço para gerenciamento de notificações
# =============================================================================

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
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
    title="Notification Service",
    description="API para gerenciamento de notificações",
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
NOTIFICATIONS_SENT = Counter('notifications_sent_total', 'Total de notificações enviadas')
NOTIFICATIONS_RETRIEVED = Counter('notifications_retrieved_total', 'Total de notificações consultadas')
NOTIFICATION_ERRORS = Counter('notification_errors_total', 'Total de erros nas notificações')

# Histogramas para latência
NOTIFICATION_DURATION = Histogram('notification_duration_seconds', 'Duração das operações de notificação')
API_REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Duração das requisições da API')

# =============================================================================
# MODELOS DE DADOS
# =============================================================================
Base = declarative_base()

class NotificationDB(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(String(50), index=True, nullable=False)
    type = Column(String(50), nullable=False)  # transaction_created, system_alert, etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="unread")  # unread, read, archived
    priority = Column(String(20), nullable=False, default="normal")  # low, normal, high, urgent
    metadata = Column(JSON)  # JSON field para metadados adicionais
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

class NotificationCreate(BaseModel):
    user_id: str = Field(..., description="ID do usuário")
    type: str = Field(..., description="Tipo da notificação")
    title: str = Field(..., max_length=200, description="Título da notificação")
    message: str = Field(..., description="Mensagem da notificação")
    priority: str = Field(default="normal", description="Prioridade da notificação")
    metadata: Optional[Dict] = Field(None, description="Metadados adicionais")
    
    @validator('priority')
    def validate_priority(cls, v):
        allowed_priorities = ['low', 'normal', 'high', 'urgent']
        if v not in allowed_priorities:
            raise ValueError(f'priority deve ser um dos seguintes: {allowed_priorities}')
        return v
    
    @validator('type')
    def validate_type(cls, v):
        allowed_types = ['transaction_created', 'system_alert', 'security_alert', 'payment_confirmation', 'general']
        if v not in allowed_types:
            raise ValueError(f'type deve ser um dos seguintes: {allowed_types}')
        return v

class NotificationResponse(BaseModel):
    id: int
    notification_id: str
    user_id: str
    type: str
    title: str
    message: str
    status: str
    priority: str
    metadata: Optional[Dict]
    created_at: datetime
    updated_at: datetime
    read_at: Optional[datetime]
    
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
def generate_notification_id() -> str:
    """Gera um ID único para notificação"""
    timestamp = int(time.time() * 1000)
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return f"NOT{timestamp}{unique_id}"

async def send_external_notification(notification_data: dict):
    """Simula envio de notificação externa (email, SMS, push)"""
    try:
        # Simular delay de envio
        await asyncio.sleep(0.1)
        
        # Log do envio
        logger.info(
            "Notificação externa enviada",
            notification_id=notification_data["notification_id"],
            user_id=notification_data["user_id"],
            type=notification_data["type"],
            priority=notification_data["priority"]
        )
        
        return True
        
    except Exception as e:
        logger.error("Erro ao enviar notificação externa", error=str(e))
        return False

# =============================================================================
# ENDPOINTS DA API
# =============================================================================
@app.get("/", response_model=Dict[str, str])
async def root():
    """Endpoint raiz da API"""
    return {
        "message": "Notification Service",
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

@app.post("/notify", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Cria uma nova notificação"""
    start_time = time.time()
    
    try:
        # Gerar ID único para notificação
        notification_id = generate_notification_id()
        
        # Criar objeto de notificação para banco
        db_notification = NotificationDB(
            notification_id=notification_id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            metadata=notification.metadata,
            status="unread"
        )
        
        # Salvar no banco
        db.add(db_notification)
        await db.commit()
        await db.refresh(db_notification)
        
        # Cache da notificação
        cache_key = f"notification:{notification_id}"
        await redis_client.setex(
            cache_key,
            3600,  # TTL de 1 hora
            str(db_notification.__dict__)
        )
        
        # Cache de notificações do usuário
        user_cache_key = f"user_notifications:{notification.user_id}"
        await redis_client.expire(user_cache_key, 0)  # Invalidar cache do usuário
        
        # Métricas
        NOTIFICATIONS_SENT.inc()
        NOTIFICATION_DURATION.observe(time.time() - start_time)
        
        # Log da notificação
        logger.info(
            "Notificação criada com sucesso",
            notification_id=notification_id,
            user_id=notification.user_id,
            type=notification.type,
            priority=notification.priority
        )
        
        # Enviar notificação externa em background
        asyncio.create_task(
            send_external_notification({
                "notification_id": notification_id,
                "user_id": notification.user_id,
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority
            })
        )
        
        return NotificationResponse.from_orm(db_notification)
        
    except Exception as e:
        NOTIFICATION_ERRORS.inc()
        logger.error("Erro ao criar notificação", error=str(e), user_id=notification.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar notificação"
        )

@app.get("/notifications/{user_id}", response_model=List[NotificationResponse])
async def get_user_notifications(
    user_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Busca todas as notificações de um usuário específico"""
    start_time = time.time()
    
    try:
        # Tentar buscar do cache primeiro
        cache_key = f"user_notifications:{user_id}"
        cached_notifications = await redis_client.get(cache_key)
        
        if cached_notifications and not status_filter:
            # TODO: Implementar deserialização do cache
            logger.info("Notificações encontradas no cache", user_id=user_id)
        
        # Construir query baseada nos filtros
        query = """
            SELECT * FROM notifications 
            WHERE user_id = :user_id AND is_active = true
        """
        params = {"user_id": user_id, "limit": limit, "offset": offset}
        
        if status_filter:
            query += " AND status = :status"
            params["status"] = status_filter
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        
        # Buscar do banco
        result = await db.execute(query, params)
        notifications = result.fetchall()
        
        # Métricas
        NOTIFICATIONS_RETRIEVED.inc()
        NOTIFICATION_DURATION.observe(time.time() - start_time)
        
        # Log da consulta
        logger.info("Notificações do usuário consultadas", user_id=user_id, count=len(notifications))
        
        # TODO: Implementar conversão para lista de NotificationResponse
        return []
        
    except Exception as e:
        NOTIFICATION_ERRORS.inc()
        logger.error("Erro ao buscar notificações do usuário", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar notificações"
        )

@app.get("/notifications/{user_id}/unread", response_model=List[NotificationResponse])
async def get_unread_notifications(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Busca notificações não lidas de um usuário"""
    try:
        result = await db.execute(
            """
            SELECT * FROM notifications 
            WHERE user_id = :user_id AND status = 'unread' AND is_active = true 
            ORDER BY created_at DESC
            """,
            {"user_id": user_id}
        )
        
        notifications = result.fetchall()
        
        logger.info("Notificações não lidas consultadas", user_id=user_id, count=len(notifications))
        
        # TODO: Implementar conversão para lista de NotificationResponse
        return []
        
    except Exception as e:
        logger.error("Erro ao buscar notificações não lidas", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar notificações"
        )

@app.put("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Marca uma notificação como lida"""
    try:
        result = await db.execute(
            """
            UPDATE notifications 
            SET status = 'read', read_at = :read_at, updated_at = :updated_at
            WHERE notification_id = :notification_id AND is_active = true
            RETURNING *
            """,
            {
                "notification_id": notification_id,
                "read_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        )
        
        notification = result.fetchone()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificação não encontrada"
            )
        
        await db.commit()
        
        # Invalidar cache
        redis_client = await get_redis()
        await redis_client.delete(f"notification:{notification_id}")
        await redis_client.delete(f"user_notifications:{notification.user_id}")
        
        logger.info("Notificação marcada como lida", notification_id=notification_id)
        
        # TODO: Implementar conversão para NotificationResponse
        return NotificationResponse(
            id=notification.id,
            notification_id=notification.notification_id,
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            status=notification.status,
            priority=notification.priority,
            metadata=notification.metadata,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
            read_at=notification.read_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao marcar notificação como lida", error=str(e), notification_id=notification_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao marcar notificação como lida"
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
    logger.info("Notification Service iniciando...")
    
    # Criar tabelas se não existirem
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Notification Service iniciado com sucesso")

@app.on_event("shutdown")
async def shutdown_event():
    """Evento executado na finalização da aplicação"""
    logger.info("Notification Service finalizando...")
    
    # Fechar conexões
    if redis_client:
        await redis_client.close()
    
    await engine.dispose()
    
    logger.info("Notification Service finalizado")

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
    uvicorn.run(app, host="0.0.0.0", port=8081)
