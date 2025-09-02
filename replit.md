# Overview

This is a Telegram bot designed to handle large file uploads (up to 4GB) with compression capabilities and cloud storage integration via Mega.nz. The bot leverages both Telegram's Bot API and MTProto (via Telethon) to overcome standard file size limitations. It provides file compression using multiple algorithms (ZIP, GZIP, LZMA), stores files on Mega.nz cloud storage, and maintains metadata for file tracking and retrieval.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework Architecture
The application uses a dual-client approach combining the official Telegram Bot API with Telethon (MTProto) to handle large file transfers. The Bot API handles standard interactions and commands, while Telethon manages files exceeding the 50MB Bot API limit.

## File Processing Pipeline
The system implements a multi-stage file processing workflow: file reception → compression (optional) → upload to Mega.nz → metadata storage → user notification. This pipeline supports asynchronous operations with progress tracking and error handling at each stage.

## Storage Strategy
Files are temporarily stored locally during processing, then uploaded to Mega.nz for permanent storage. Local metadata is maintained in JSON format to track file ownership, compression details, and download links. The system generates unique file IDs for user-friendly file retrieval.

## Compression System
The application supports multiple compression algorithms (ZIP, GZIP, LZMA) with configurable compression levels. Users can set preferences for automatic compression, and the system calculates compression ratios to provide feedback on space savings.

## Configuration Management
Environment-based configuration system handles sensitive credentials and operational parameters. Required settings include Telegram API credentials, Mega.nz login details, and optional storage channel configuration for file mirroring.

## Error Handling and Logging
Comprehensive logging system tracks operations, errors, and user interactions. The application includes graceful error handling for network issues, file system errors, and API limitations.

# External Dependencies

## Telegram Integration
- **python-telegram-bot**: Official Bot API wrapper for command handling and user interactions
- **Telethon**: MTProto client library for large file transfers and advanced Telegram features
- Requires Bot API token, API ID, and API hash from Telegram

## Cloud Storage
- **mega.py**: Python SDK for Mega.nz API integration
- Requires Mega.nz account credentials for file storage and retrieval
- Handles file upload, download, and link generation

## File Processing
- **zipfile**: Built-in Python library for ZIP compression
- **gzip**: Built-in Python library for GZIP compression  
- **lzma**: Built-in Python library for LZMA compression
- Standard library modules for file system operations and async processing

## Runtime Environment
- **asyncio**: Asynchronous programming support for concurrent operations
- **logging**: Application logging and monitoring
- **os/dataclasses**: Environment variable handling and configuration management