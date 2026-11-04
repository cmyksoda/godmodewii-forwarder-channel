# IOS starts a NAND title at 0x3400 in real mode; set up memory as libogc expects, then enter __app_start.
	.section .stub,"ax",@progbits
	.globl nand_boot_stub
nand_boot_stub:
	lis	3,0x0011
	ori	3,3,0x0c64
	mtspr	1008,3			# HID0
	isync
	li	4,0x2000		# MSR: floating point on, translation off
	mtmsr	4
	ori	3,3,0xc000		# HID0: enable and invalidate the caches
	mtspr	1008,3
	isync

	li	4,0
	.irp	spr, 528,530,532,534, 536,538,540,542, 560,562, 568,570
	mtspr	\spr,4			# every BAT upper word: invalid
	.endr
	isync
	lis	4,0x8000
	.irp	sr, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
	mtsr	\sr,4
	.endr
	isync

	.macro	bat upper, lower, eff, phys
	lis	3,\eff
	ori	3,3,0x1fff		# 256 MB, valid in both modes
	lis	4,\phys
	ori	4,4,\lower
	mtspr	\upper+1,4
	mtspr	\upper,3
	.endm
	bat	528, 0x02, 0x8000, 0x0000	# IBAT0: MEM1 cached
	bat	536, 0x02, 0x8000, 0x0000	# DBAT0
	bat	538, 0x2a, 0xc000, 0x0000	# DBAT1: MEM1 uncached
	bat	560, 0x02, 0x9000, 0x1000	# IBAT4: MEM2 cached
	bat	568, 0x02, 0x9000, 0x1000	# DBAT4
	bat	570, 0x2a, 0xd000, 0x1000	# DBAT5: MEM2 uncached
	isync

	li	3,0x1f			# BAT3: identity-map the first 1 MB so this code survives
	li	4,0x01
	mtspr	535,4
	mtspr	534,3
	mtspr	543,4
	mtspr	542,3
	isync

	mfmsr	4
	ori	4,4,0x30		# translation on
	mtmsr	4
	isync

	lis	3,0x8000
	li	4,0
	stw	4,0xf4(3)
	lis	3,__app_start@h
	ori	3,3,__app_start@l
	mtctr	3
	bctr

# A self-contained "sc" handler, as older libogc left at 0xC00. dolxz-packed apps (GodModeWii) make a
# system call before installing their own, and libogc 3's vector would jump into this forwarder's dead code.
	.section .rodata
	.balign	4
	.globl	sc_handler, sc_handler_end
sc_handler:
	mtspr	274,9			# SPRG2
	mtspr	275,10			# SPRG3
	mfspr	9,1008			# HID0
	ori	10,9,0x0008		# ABE: broadcast the sync
	mtspr	1008,10
	isync
	sync
	mtspr	1008,9
	mfspr	9,274
	mfspr	10,275
	rfi
sc_handler_end:
