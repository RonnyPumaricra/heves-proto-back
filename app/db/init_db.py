from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.area import Area
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.device import Device
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.ticket_survey import TicketSurvey
from app.models.user import User
from app.services.sla import apply_sla


def _ago(days: int, hours: int = 0, minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)


# ---------------------------------------------------------------------------
# Datos maestros
# ---------------------------------------------------------------------------

SLA_DEFAULTS = {
    "critica": (15, 120),
    "alta": (60, 480),
    "media": (240, 1440),
    "baja": (480, 2880),
}

AREAS = [
    "Aulas",
    "Laboratorios",
    "Biblioteca",
    "Secretaría Académica",
    "Coordinación",
    "Sala de Docentes",
    "Servicios Web",
]

DEVICES = [
    ("PC Aula 302", "PC", "Aulas", "Aula 302"),
    ("Proyector Aula 302", "Proyector", "Aulas", "Aula 302"),
    ("PC Lab Redes", "PC", "Laboratorios", "Laboratorio de Redes"),
    ("PC Lab Software", "PC", "Laboratorios", "Laboratorio de Software"),
    ("PC Biblioteca 1", "PC", "Biblioteca", "Sala de lectura"),
    ("Impresora Biblioteca", "Impresora", "Biblioteca", "Mostrador"),
    ("PC Secretaría 1", "PC", "Secretaría Académica", "Ventanilla 1"),
    ("PC Coordinación", "PC", "Coordinación", "Oficina principal"),
]

SEED_USERS = [
    ("Administrador Sistema", "admin@untels.edu.pe", "admin123", "admin", None),
    ("Supervisor de Soporte", "supervisor@untels.edu.pe", "supervisor123", "supervisor", None),
    ("Técnico de Soporte", "tecnico@untels.edu.pe", "tecnico123", "tecnico", None),
    ("Estudiante Demo", "estudiante@untels.edu.pe", "estudiante123", "usuario", "Aulas"),
    ("Docente Demo", "docente@untels.edu.pe", "docente123", "usuario", "Sala de Docentes"),
]

# ---------------------------------------------------------------------------
# Tickets: (title, description, priority, status, area, reporter_email,
#           assigned_email, device_name, created_days_ago)
# ---------------------------------------------------------------------------

SEED_TICKETS = [
    # --- CERRADO (4) ---
    (
        "No enciende PC Aula 302",
        "La computadora del Aula 302 no enciende al presionar el boton de encendido. No muestra ninguna luz LED.",
        "alta",
        "CERRADO",
        "Aulas",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "PC Aula 302",
        10,
    ),
    (
        "Proyector sin imagen en Aula 302",
        "El proyector del Aula 302 enciende pero no muestra imagen. Se ve una pantalla azul con ruido estatico.",
        "media",
        "CERRADO",
        "Aulas",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "Proyector Aula 302",
        9,
    ),
    (
        "Sonido no funciona en Aula 302",
        "Los altavoces del aula no producen sonido. Los estudiantes no pueden escuchar videos en clase.",
        "baja",
        "CERRADO",
        "Aulas",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        8,
    ),
    (
        "Cambio de contrasena Blackboard",
        "El estudiante olvido su contrasena de Blackboard y necesita recuperar acceso para entregar tareas.",
        "baja",
        "CERRADO",
        "Servicios Web",
        "estudiante@untels.edu.pe",
        "supervisor@untels.edu.pe",
        None,
        7,
    ),
    # --- RESUELTO (4) ---
    (
        "Impresora no responde en Biblioteca",
        "La impresora del mostrador de la Biblioteca no imprime. Muestra un error de papel atascado.",
        "alta",
        "RESUELTO",
        "Biblioteca",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "Impresora Biblioteca",
        5,
    ),
    (
        "Lentitud en PC Lab Software",
        "La computadora del Laboratorio de Software esta muy lenta. Tarda mas de 5 minutos en iniciar Windows.",
        "media",
        "RESUELTO",
        "Laboratorios",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "PC Lab Software",
        4,
    ),
    (
        "Teclado danado Lab Software",
        "El teclado del Laboratorio de Software tiene varias teclas que no responden (Q, W, E, R).",
        "media",
        "RESUELTO",
        "Laboratorios",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "PC Lab Software",
        3,
    ),
    (
        "Scanner no detectado en Biblioteca",
        "El escaner de la Biblioteca no es detectado por el sistema operativo. Aparece como dispositivo desconocido.",
        "baja",
        "RESUELTO",
        "Biblioteca",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        3,
    ),
    # --- EN_PROCESO (4) ---
    (
        "Error al acceder al SIU",
        "Varios docentes reportan que no pueden acceder al Sistema de Informacion Universitaria. Muestra error 503.",
        "critica",
        "EN_PROCESO",
        "Servicios Web",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        2,
    ),
    (
        "WiFi cae intermitentemente en Aulas",
        "El WiFi de las aulas se desconecta cada 10 minutos. Afecta a todos los dispositivos moviles.",
        "critica",
        "EN_PROCESO",
        "Aulas",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        2,
    ),
    (
        "PC no prende en Secretaria",
        "La PC de la Ventanilla 1 de Secretaria Academica no enciende. La secretaria no puede atender.",
        "media",
        "EN_PROCESO",
        "Secretaría Académica",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "PC Secretaría 1",
        1,
    ),
    (
        "No imprime en Biblioteca",
        "La impresora de la Biblioteca no responde a solicitudes de impresion desde ningun equipo.",
        "alta",
        "EN_PROCESO",
        "Biblioteca",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "Impresora Biblioteca",
        1,
    ),
    # --- ASIGNADO (4) ---
    (
        "Cuenta bloqueada Blackboard",
        "El estudiante tiene la cuenta bloqueada despues de 3 intentos fallidos de inicio de sesion.",
        "alta",
        "ASIGNADO",
        "Servicios Web",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        1,
    ),
    (
        "Proyector falla intermitente",
        "El proyector del Aula 302 se apaga aleatoriamente durante las presentaciones.",
        "media",
        "ASIGNADO",
        "Aulas",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "Proyector Aula 302",
        1,
    ),
    (
        "No accede a correo institucional",
        "El docente no puede acceder a su correo institucional. La pagina no carga.",
        "baja",
        "ASIGNADO",
        "Sala de Docentes",
        "docente@untels.edu.pe",
        "tecnico@untels.edu.pe",
        None,
        1,
    ),
    (
        "Mouse no funciona Lab Redes",
        "El mouse del Laboratorio de Redes no mueve el cursor. Se congela cada pocos segundos.",
        "baja",
        "ASIGNADO",
        "Laboratorios",
        "estudiante@untels.edu.pe",
        "tecnico@untels.edu.pe",
        "PC Lab Redes",
        1,
    ),
    # --- CREADO (4) ---
    (
        "Solicita instalacion de software",
        "El docente solicita la instalacion de MATLAB en el Laboratorio de Software para el semestre.",
        "baja",
        "CREADO",
        "Laboratorios",
        "docente@untels.edu.pe",
        None,
        "PC Lab Software",
        0,
    ),
    (
        "Pantalla azul PC Coordinacion",
        "La PC de Coordinacion muestra pantalla azul (BSOD) al iniciar. Error SYSTEM_SERVICE_EXCEPTION.",
        "alta",
        "CREADO",
        "Coordinación",
        "docente@untels.edu.pe",
        None,
        "PC Coordinación",
        0,
    ),
    (
        "No carga pagina web universitaria",
        "La pagina web de la universidad no carga. Muestra timeout despues de 30 segundos.",
        "media",
        "CREADO",
        "Servicios Web",
        "estudiante@untels.edu.pe",
        None,
        None,
        0,
    ),
    (
        "Impresora atascada Biblioteca",
        "La impresora de la Biblioteca tiene papel atascado y no puede imprimir.",
        "alta",
        "CREADO",
        "Biblioteca",
        "estudiante@untels.edu.pe",
        None,
        "Impresora Biblioteca",
        0,
    ),
]

# ---------------------------------------------------------------------------
# Comments: (ticket_idx, author_email, body, days_ago, hours_offset)
# ---------------------------------------------------------------------------

SEED_COMMENTS = [
    (0, "tecnico@untels.edu.pe", "Verifique la PC. El problema es la fuente de poder. La cambie con una de repuesto.", 9, 2),
    (0, "estudiante@untels.edu.pe", "Gracias tecnico, ya enciende perfectamente.", 9, 5),
    (1, "tecnico@untels.edu.pe", "El proyector tenia el cable VGA danado. Lo reemplace y funciona correctamente.", 8, 3),
    (1, "docente@untels.edu.pe", "Confirmo, el proyector ya muestra imagen. Muchas gracias.", 8, 6),
    (2, "tecnico@untels.edu.pe", "Los altavoces estaban desconectados. Los reconecte y el sonido funciona.", 7, 1),
    (3, "supervisor@untels.edu.pe", "Se genero una contrasena temporal y se envio al correo del estudiante.", 6, 1),
    (3, "estudiante@untels.edu.pe", "Ya pude ingresar con la contrasena temporal. Muchas gracias.", 6, 2),
    (4, "tecnico@untels.edu.pe", "Retire el papel atascado y limpie los rodillos. La impresora esta operativa.", 4, 2),
    (4, "estudiante@untels.edu.pe", "Probe imprimir y funciona bien. Solo tarda un poco en calentar.", 4, 4),
    (5, "tecnico@untels.edu.pe", "La PC tenia demasiados programas en inicio. Limpi el registro y deshabilite programas innecesarios.", 3, 3),
    (5, "estudiante@untels.edu.pe", "Ahora la PC inicia mucho mas rapido. Gracias.", 3, 5),
    (6, "tecnico@untels.edu.pe", "Cambie el teclado danado por uno nuevo del almacen.", 2, 2),
    (7, "tecnico@untels.edu.pe", "Instale los drivers correctos del escaner. Ya es detectado por el sistema.", 2, 4),
    (8, "tecnico@untels.edu.pe", "Reporte el problema al equipo de sistemas. Parece ser un issue con el servidor.", 1, 3),
    (8, "supervisor@untels.edu.pe", "Escalado al area de desarrollo. Estan revisando los logs del servidor.", 1, 5),
    (9, "tecnico@untels.edu.pe", "Revis los access points del piso 2. Varios estaban con firmware desactualizado.", 1, 2),
    (9, "estudiante@untels.edu.pe", "El problema persiste, se cae cada vez que entro a YouTube en el celular.", 1, 6),
    (10, "tecnico@untels.edu.pe", "Verifique la fuente de poder de la PC. No enciende ni con otro cable.", 1, 2),
    (11, "tecnico@untels.edu.pe", "La impresora tiene un error E-3 en la pantalla. Revisare el manual.", 1, 3),
    (12, "supervisor@untels.edu.pe", "Asignado a tecnico para verificacion de cuenta.", 1, 1),
    (13, "tecnico@untels.edu.pe", "Revisare el proyector esta tarde cuando libere el aula.", 1, 2),
    (14, "supervisor@untels.edu.pe", "Ticket asignado. El tecnico revisara el problema de conexion.", 1, 1),
    (15, "tecnico@untels.edu.pe", "Verificare el mouse con otro equipo para descartar problema de hardware.", 1, 2),
]

# ---------------------------------------------------------------------------
# History: (ticket_idx, actor_email, field, old_value, new_value, days_ago, hours_offset)
# ---------------------------------------------------------------------------

SEED_HISTORY = [
    (0, "estudiante@untels.edu.pe", "status", None, "CREADO", 10, 0),
    (0, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 10, 1),
    (0, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 10, 2),
    (0, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 9, 4),
    (0, "estudiante@untels.edu.pe", "status", "RESUELTO", "CERRADO", 9, 6),
    (1, "docente@untels.edu.pe", "status", None, "CREADO", 9, 0),
    (1, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 9, 1),
    (1, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 8, 2),
    (1, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 8, 4),
    (1, "docente@untels.edu.pe", "status", "RESUELTO", "CERRADO", 8, 7),
    (2, "docente@untels.edu.pe", "status", None, "CREADO", 8, 0),
    (2, "tecnico@untels.edu.pe", "status", "CREADO", "ASIGNADO", 8, 1),
    (2, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 7, 1),
    (2, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 7, 2),
    (2, "docente@untels.edu.pe", "status", "RESUELTO", "CERRADO", 7, 3),
    (3, "estudiante@untels.edu.pe", "status", None, "CREADO", 7, 0),
    (3, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 7, 0),
    (3, "supervisor@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 6, 1),
    (3, "supervisor@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 6, 2),
    (3, "estudiante@untels.edu.pe", "status", "RESUELTO", "CERRADO", 6, 3),
    (4, "estudiante@untels.edu.pe", "status", None, "CREADO", 5, 0),
    (4, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 5, 1),
    (4, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 4, 2),
    (4, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 4, 4),
    (5, "estudiante@untels.edu.pe", "status", None, "CREADO", 4, 0),
    (5, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 4, 1),
    (5, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 3, 2),
    (5, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 3, 5),
    (6, "docente@untels.edu.pe", "status", None, "CREADO", 3, 0),
    (6, "tecnico@untels.edu.pe", "status", "CREADO", "ASIGNADO", 3, 1),
    (6, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 2, 2),
    (6, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 2, 3),
    (7, "docente@untels.edu.pe", "status", None, "CREADO", 3, 0),
    (7, "tecnico@untels.edu.pe", "status", "CREADO", "ASIGNADO", 3, 1),
    (7, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 2, 3),
    (7, "tecnico@untels.edu.pe", "status", "EN_PROCESO", "RESUELTO", 2, 5),
    (8, "docente@untels.edu.pe", "status", None, "CREADO", 2, 0),
    (8, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 2, 1),
    (8, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 2, 3),
    (9, "estudiante@untels.edu.pe", "status", None, "CREADO", 2, 0),
    (9, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 2, 0),
    (9, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 2, 2),
    (10, "docente@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (10, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
    (10, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 1, 2),
    (11, "estudiante@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (11, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
    (11, "tecnico@untels.edu.pe", "status", "ASIGNADO", "EN_PROCESO", 1, 3),
    (12, "estudiante@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (12, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
    (13, "docente@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (13, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
    (14, "estudiante@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (14, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
    (15, "estudiante@untels.edu.pe", "status", None, "CREADO", 1, 0),
    (15, "supervisor@untels.edu.pe", "status", "CREADO", "ASIGNADO", 1, 1),
]

# ---------------------------------------------------------------------------
# Surveys: (ticket_idx, rating, comment, days_ago)
# Solo tickets CERRADO o RESUELTO
# ---------------------------------------------------------------------------

SEED_SURVEYS = [
    (0, 5, "Excelente servicio, rapido y efectivo.", 9),
    (1, 5, "Muy bien, el tecnico fue puntual y profesional.", 8),
    (2, 4, "Bien, resolvio el problema rapidamente.", 7),
    (3, 5, "Perfecto, me ayudaron a recuperar mi acceso.", 6),
    (4, 4, "La impresora funciona pero tardo un poco mas de lo esperado.", 4),
    (5, 5, "Increible, la PC parece nueva. Muchas gracias.", 3),
    (6, 4, "El teclado funciona perfecto.", 2),
    (7, 4, "El escaner ya es detectado correctamente.", 2),
]

# ---------------------------------------------------------------------------
# Attachments: (ticket_idx, filename, path, days_ago)
# ---------------------------------------------------------------------------

SEED_ATTACHMENTS = [
    (0, "pc_no_enciende.jpg", "uploads/seed/pc_no_enciende.jpg", 10),
    (4, "error_impresora.jpg", "uploads/seed/error_impresora.jpg", 5),
    (8, "error_siu_503.png", "uploads/seed/error_siu_503.png", 2),
    (9, "wifi_disconnect_log.txt", "uploads/seed/wifi_disconnect_log.txt", 2),
    (17, "bsod_coordinacion.jpg", "uploads/seed/bsod_coordinacion.jpg", 0),
]


# ===========================================================================
# Funciones helper get-or-create
# ===========================================================================


def _get_or_create_area(db: Session, name: str) -> Area:
    a = db.query(Area).filter(Area.name == name).first()
    if a:
        return a
    a = Area(name=name)
    db.add(a)
    db.flush()
    return a


def _get_or_create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
    area: Area | None = None,
) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u:
        return u
    u = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        area_id=area.id if area else None,
    )
    db.add(u)
    db.flush()
    return u


def _get_or_create_device(
    db: Session, *, name: str, device_type: str, area: Area, location: str
) -> Device:
    d = db.query(Device).filter(Device.name == name).first()
    if d:
        return d
    d = Device(
        name=name,
        device_type=device_type,
        area_id=area.id,
        location=location,
    )
    db.add(d)
    db.flush()
    return d


def _get_or_create_sla(db: Session, priority: str, response: int, resolution: int) -> SLAPolicy:
    p = db.get(SLAPolicy, priority)
    if p:
        return p
    p = SLAPolicy(
        priority=priority, response_minutes=response, resolution_minutes=resolution
    )
    db.add(p)
    db.flush()
    return p


def _get_or_create_ticket(
    db: Session,
    *,
    title: str,
    description: str,
    priority: str,
    status: str,
    area: Area | None,
    reporter: User,
    assigned_to: User | None,
    device: Device | None,
    created_at: datetime,
) -> Ticket:
    t = db.query(Ticket).filter(Ticket.title == title).first()
    if t:
        return t
    t = Ticket(
        title=title,
        description=description,
        priority=priority,
        status=status,
        area_id=area.id if area else None,
        reporter_id=reporter.id,
        assigned_to_id=assigned_to.id if assigned_to else None,
        device_id=device.id if device else None,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(t)
    db.flush()
    apply_sla(db, t)

    if status in ("ASIGNADO", "EN_PROCESO", "RESUELTO", "CERRADO"):
        t.first_assigned_at = created_at + timedelta(hours=1)
    if status in ("RESUELTO", "CERRADO"):
        t.resolved_at = created_at + timedelta(days=1)
    if status == "CERRADO":
        t.closed_at = created_at + timedelta(days=1, hours=2)

    db.flush()
    return t


def _get_or_create_comment(
    db: Session,
    *,
    ticket: Ticket,
    author: User,
    body: str,
    created_at: datetime,
) -> Comment:
    existing = (
        db.query(Comment)
        .filter(Comment.ticket_id == ticket.id, Comment.body == body)
        .first()
    )
    if existing:
        return existing
    c = Comment(
        ticket_id=ticket.id,
        author_id=author.id,
        body=body,
        created_at=created_at,
    )
    db.add(c)
    db.flush()
    return c


def _get_or_create_history(
    db: Session,
    *,
    ticket: Ticket,
    actor: User,
    field: str,
    old_value: str | None,
    new_value: str | None,
    created_at: datetime,
) -> TicketHistory:
    existing = (
        db.query(TicketHistory)
        .filter(
            TicketHistory.ticket_id == ticket.id,
            TicketHistory.field == field,
            TicketHistory.new_value == new_value,
        )
        .first()
    )
    if existing:
        return existing
    h = TicketHistory(
        ticket_id=ticket.id,
        actor_id=actor.id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        created_at=created_at,
    )
    db.add(h)
    db.flush()
    return h


def _get_or_create_survey(
    db: Session,
    *,
    ticket: Ticket,
    rating: int,
    comment_text: str | None,
    created_at: datetime,
) -> TicketSurvey:
    existing = db.query(TicketSurvey).filter(TicketSurvey.ticket_id == ticket.id).first()
    if existing:
        return existing
    s = TicketSurvey(
        ticket_id=ticket.id,
        rating=rating,
        comment=comment_text,
        created_at=created_at,
    )
    db.add(s)
    db.flush()
    return s


def _get_or_create_attachment(
    db: Session,
    *,
    ticket: Ticket,
    filename: str,
    path: str,
    created_at: datetime,
) -> Attachment:
    existing = (
        db.query(Attachment)
        .filter(Attachment.ticket_id == ticket.id, Attachment.filename == filename)
        .first()
    )
    if existing:
        return existing
    a = Attachment(
        ticket_id=ticket.id,
        filename=filename,
        path=path,
        created_at=created_at,
    )
    db.add(a)
    db.flush()
    return a


# ===========================================================================
# Seed principal
# ===========================================================================


def seed() -> dict:
    db = SessionLocal()
    try:
        # 1. Areas
        areas = {name: _get_or_create_area(db, name) for name in AREAS}

        # 2. SLA
        for priority, (resp, resol) in SLA_DEFAULTS.items():
            _get_or_create_sla(db, priority, resp, resol)

        # 3. Usuarios
        users = {}
        for full_name, email, password, role, area_name in SEED_USERS:
            u = _get_or_create_user(
                db,
                full_name=full_name,
                email=email,
                password=password,
                role=role,
                area=areas.get(area_name) if area_name else None,
            )
            users[email] = u

        # 4. Dispositivos
        devices = {}
        for name, dtype, area_name, location in DEVICES:
            d = _get_or_create_device(
                db, name=name, device_type=dtype, area=areas[area_name], location=location
            )
            devices[name] = d

        # 5. Tickets
        tickets = []
        for (
            title,
            description,
            priority,
            status,
            area_name,
            reporter_email,
            assigned_email,
            device_name,
            days_ago,
        ) in SEED_TICKETS:
            t = _get_or_create_ticket(
                db,
                title=title,
                description=description,
                priority=priority,
                status=status,
                area=areas.get(area_name),
                reporter=users[reporter_email],
                assigned_to=users.get(assigned_email) if assigned_email else None,
                device=devices.get(device_name) if device_name else None,
                created_at=_ago(days_ago),
            )
            tickets.append(t)

        # 6. Historial
        for ticket_idx, actor_email, field, old_val, new_val, days_ago, hours in SEED_HISTORY:
            _get_or_create_history(
                db,
                ticket=tickets[ticket_idx],
                actor=users[actor_email],
                field=field,
                old_value=old_val,
                new_value=new_val,
                created_at=_ago(days_ago, hours),
            )

        # 7. Comentarios
        for ticket_idx, author_email, body, days_ago, hours in SEED_COMMENTS:
            _get_or_create_comment(
                db,
                ticket=tickets[ticket_idx],
                author=users[author_email],
                body=body,
                created_at=_ago(days_ago, hours),
            )

        # 8. Encuestas
        for ticket_idx, rating, comment_text, days_ago in SEED_SURVEYS:
            _get_or_create_survey(
                db,
                ticket=tickets[ticket_idx],
                rating=rating,
                comment_text=comment_text,
                created_at=_ago(days_ago),
            )

        # 9. Adjuntos
        for ticket_idx, filename, path, days_ago in SEED_ATTACHMENTS:
            _get_or_create_attachment(
                db,
                ticket=tickets[ticket_idx],
                filename=filename,
                path=path,
                created_at=_ago(days_ago),
            )

        db.commit()
        return {
            "areas": len(areas),
            "users": len(SEED_USERS),
            "devices": len(DEVICES),
            "tickets": len(SEED_TICKETS),
            "history": len(SEED_HISTORY),
            "comments": len(SEED_COMMENTS),
            "surveys": len(SEED_SURVEYS),
            "attachments": len(SEED_ATTACHMENTS),
        }
    finally:
        db.close()
