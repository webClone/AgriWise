import struct
import zlib

def decode_tiff(raw_bytes: bytes) -> bytes:
    """Extracts raw pixel data from a Sentinel Hub single-strip TIFF (uncompressed or Deflate)."""
    # 1. Header (8 bytes)
    # Byte order: 'II' (little-endian) or 'MM' (big-endian)
    if len(raw_bytes) < 8:
        raise ValueError("File too small to be a TIFF")
        
    byte_order = raw_bytes[:2]
    if byte_order == b'II':
        endian = '<'
    elif byte_order == b'MM':
        endian = '>'
    else:
        raise ValueError(f"Invalid TIFF byte order: {byte_order}")
        
    magic = struct.unpack(f"{endian}H", raw_bytes[2:4])[0]
    if magic != 42:
        raise ValueError(f"Invalid TIFF magic number: {magic}")
        
    ifd_offset = struct.unpack(f"{endian}I", raw_bytes[4:8])[0]
    
    # 2. IFD
    num_entries = struct.unpack(f"{endian}H", raw_bytes[ifd_offset:ifd_offset+2])[0]
    
    strip_offsets = []
    strip_byte_counts = []
    compression = 1 # Default uncompressed
    
    for i in range(num_entries):
        entry_offset = ifd_offset + 2 + (i * 12)
        tag, dtype, count, value_offset = struct.unpack(f"{endian}HHII", raw_bytes[entry_offset:entry_offset+12])
        
        # tag 259: Compression
        if tag == 259:
            # Short (count=1), value is in the value_offset field itself
            compression = value_offset & 0xFFFF
            
        # tag 273: StripOffsets
        elif tag == 273:
            if count == 1:
                strip_offsets = [value_offset]
            else:
                # If multiple offsets, value_offset points to an array
                strip_offsets = list(struct.unpack(f"{endian}{count}I", raw_bytes[value_offset:value_offset+count*4]))
                
        # tag 279: StripByteCounts
        elif tag == 279:
            # Could be Short or Long
            if count == 1:
                if dtype == 3: # Short
                    strip_byte_counts = [value_offset & 0xFFFF]
                else: # Long
                    strip_byte_counts = [value_offset]
            else:
                if dtype == 3: # Short
                    strip_byte_counts = list(struct.unpack(f"{endian}{count}H", raw_bytes[value_offset:value_offset+count*2]))
                else: # Long
                    strip_byte_counts = list(struct.unpack(f"{endian}{count}I", raw_bytes[value_offset:value_offset+count*4]))

    if not strip_offsets or not strip_byte_counts:
        raise ValueError("No StripOffsets or StripByteCounts found in TIFF")
        
    extracted_data = bytearray()
    
    for offset, length in zip(strip_offsets, strip_byte_counts):
        strip_data = raw_bytes[offset:offset+length]
        
        if compression == 1: # Uncompressed
            extracted_data.extend(strip_data)
        elif compression == 8: # Deflate
            extracted_data.extend(zlib.decompress(strip_data))
        elif compression == 5: # LZW
            raise ValueError("LZW compression not implemented")
        else:
            raise ValueError(f"Unsupported compression type: {compression}")
            
    return bytes(extracted_data)

if __name__ == "__main__":
    with open("test_parse_tar.py", "rb") as f:
        print("Run me with a valid tiff file")
