from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


class Channel(str, Enum):
    email = 'email'
    sms = 'sms'
    push = 'push'


class SendResult(BaseModel):
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EmailPayload(BaseModel):
    to: List[EmailStr]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    from_email: Optional[EmailStr] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    reply_to: Optional[EmailStr] = None


class SMSPayload(BaseModel):
    to: str = Field(description='E.164 phone number')
    text: str
    from_number: Optional[str] = None


class PushPayload(BaseModel):
    token: str
    title: Optional[str] = None
    body: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class NotificationRequest(BaseModel):
    channels: List[Channel]
    email: Optional[EmailPayload] = None
    sms: Optional[SMSPayload] = None
    push: Optional[PushPayload] = None


class NotificationResponse(BaseModel):
    results: Dict[Channel, SendResult]

