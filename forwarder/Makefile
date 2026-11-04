CC      := $(DEVKITPPC)/bin/powerpc-eabi-gcc
ELF2DOL := $(DEVKITPRO)/tools/bin/elf2dol
OGC     := $(DEVKITPRO)/libogc
CFLAGS  := -Os -Wall -DGEKKO -mrvl -mcpu=750 -meabi -mhard-float -I$(OGC)/include
LDFLAGS := -mrvl -Wl,--section-start,.stub=0x80003400 -L$(OGC)/lib/wii

forwarder.dol: forwarder.elf
	$(ELF2DOL) $< $@

forwarder.elf: stub.S main.c
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -lfat -logc -o $@

clean:
	rm -f forwarder.elf forwarder.dol
