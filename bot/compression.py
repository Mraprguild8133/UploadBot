"""
File compression utilities supporting multiple algorithms.
Handles ZIP, GZIP, and LZMA compression with progress tracking.
"""

import asyncio
import gzip
import lzma
import logging
import os
import zipfile
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class CompressionManager:
    def __init__(self, config):
        self.config = config
        self.supported_algorithms = ['zip', 'gzip', 'lzma']
    
    async def compress_file(self, input_path: str, algorithm: str = 'zip', level: int = 6) -> str:
        """
        Compress a file using the specified algorithm.
        
        Args:
            input_path: Path to input file
            algorithm: Compression algorithm ('zip', 'gzip', 'lzma')
            level: Compression level (1-9)
            
        Returns:
            Path to compressed file
        """
        if algorithm not in self.supported_algorithms:
            raise ValueError(f"Unsupported compression algorithm: {algorithm}")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Generate output filename
        base_name = os.path.basename(input_path)
        output_path = os.path.join(
            os.path.dirname(input_path),
            f"{base_name}.{algorithm}"
        )
        
        logger.info(f"Compressing {input_path} using {algorithm} (level {level})")
        
        try:
            if algorithm == 'zip':
                await self._compress_zip(input_path, output_path, level)
            elif algorithm == 'gzip':
                await self._compress_gzip(input_path, output_path, level)
            elif algorithm == 'lzma':
                await self._compress_lzma(input_path, output_path, level)
            
            logger.info(f"Compression complete: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            # Cleanup partial file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise
    
    async def decompress_file(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Decompress a file based on its extension.
        
        Args:
            input_path: Path to compressed file
            output_path: Optional output path (auto-generated if None)
            
        Returns:
            Path to decompressed file
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Compressed file not found: {input_path}")
        
        # Determine compression type from extension
        if input_path.endswith('.zip'):
            algorithm = 'zip'
        elif input_path.endswith('.gz') or input_path.endswith('.gzip'):
            algorithm = 'gzip'
        elif input_path.endswith('.xz') or input_path.endswith('.lzma'):
            algorithm = 'lzma'
        else:
            raise ValueError(f"Unable to determine compression type from filename: {input_path}")
        
        # Generate output path if not provided
        if output_path is None:
            if algorithm == 'zip':
                # For ZIP, we'll extract to a directory and return the first file
                output_dir = input_path.rsplit('.', 1)[0] + '_extracted'
                os.makedirs(output_dir, exist_ok=True)
                output_path = output_dir
            else:
                # For GZIP/LZMA, remove the compression extension
                output_path = input_path.rsplit('.', 1)[0]
        
        logger.info(f"Decompressing {input_path} using {algorithm}")
        
        try:
            if algorithm == 'zip':
                return await self._decompress_zip(input_path, output_path)
            elif algorithm == 'gzip':
                await self._decompress_gzip(input_path, output_path)
                return output_path
            elif algorithm == 'lzma':
                await self._decompress_lzma(input_path, output_path)
                return output_path
                
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            raise
    
    async def _compress_zip(self, input_path: str, output_path: str, level: int):
        """Compress file using ZIP algorithm."""
        def _zip_compress():
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as zf:
                zf.write(input_path, os.path.basename(input_path))
        
        await asyncio.get_event_loop().run_in_executor(None, _zip_compress)
    
    async def _compress_gzip(self, input_path: str, output_path: str, level: int):
        """Compress file using GZIP algorithm."""
        def _gzip_compress():
            with open(input_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb', compresslevel=level) as f_out:
                    while True:
                        chunk = f_in.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        await asyncio.get_event_loop().run_in_executor(None, _gzip_compress)
    
    async def _compress_lzma(self, input_path: str, output_path: str, level: int):
        """Compress file using LZMA algorithm."""
        def _lzma_compress():
            with open(input_path, 'rb') as f_in:
                with lzma.open(output_path, 'wb', preset=level) as f_out:
                    while True:
                        chunk = f_in.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        await asyncio.get_event_loop().run_in_executor(None, _lzma_compress)
    
    async def _decompress_zip(self, input_path: str, output_dir: str) -> str:
        """Decompress ZIP file and return path to extracted file."""
        def _zip_decompress():
            with zipfile.ZipFile(input_path, 'r') as zf:
                # Extract all files
                zf.extractall(output_dir)
                # Return path to the first extracted file
                extracted_files = zf.namelist()
                if extracted_files:
                    return os.path.join(output_dir, extracted_files[0])
                else:
                    raise ValueError("ZIP file is empty")
        
        return await asyncio.get_event_loop().run_in_executor(None, _zip_decompress)
    
    async def _decompress_gzip(self, input_path: str, output_path: str):
        """Decompress GZIP file."""
        def _gzip_decompress():
            with gzip.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        await asyncio.get_event_loop().run_in_executor(None, _gzip_decompress)
    
    async def _decompress_lzma(self, input_path: str, output_path: str):
        """Decompress LZMA file."""
        def _lzma_decompress():
            with lzma.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        f_out.write(chunk)
        
        await asyncio.get_event_loop().run_in_executor(None, _lzma_decompress)
    
    def get_compression_info(self, original_size: int, compressed_size: int) -> dict:
        """Calculate compression statistics."""
        if original_size == 0:
            ratio = 0
        else:
            ratio = (1 - compressed_size / original_size) * 100
        
        return {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': ratio,
            'space_saved': original_size - compressed_size
        }
    
    def recommend_algorithm(self, file_path: str, file_size: int) -> str:
        """Recommend compression algorithm based on file type and size."""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Text files: GZIP is usually best
        text_extensions = ['.txt', '.log', '.csv', '.json', '.xml', '.html', '.css', '.js', '.py', '.md']
        if file_ext in text_extensions:
            return 'gzip'
        
        # Already compressed files: ZIP for compatibility
        compressed_extensions = ['.jpg', '.png', '.mp3', '.mp4', '.zip', '.rar', '.7z']
        if file_ext in compressed_extensions:
            return 'zip'  # Minimal additional compression but good compatibility
        
        # Large files: LZMA for best compression
        if file_size > 100 * 1024 * 1024:  # 100MB
            return 'lzma'
        
        # Default: ZIP for good balance
        return 'zip'
