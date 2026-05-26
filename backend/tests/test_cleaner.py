from app.services.cleaner import clean_context, extract_register_summary

context = """
UM10139 All information provided in this document is subject to legal disclaimers.  NXP B.V. 2012. All rights reserved.
User manual Rev. 4  23 April 2012 287 of 354
NXP Semiconductors UM10139
Chapter 19: LPC214x ADC
19.4 Register description
The A/D Converter registers are shown in Table 279.
[1] Reset value reflects the data stored in used bits only. It does not include reserved bits content.
Table 279. ADC registers
Generic Name Description Access Reset value [1] AD0 Address & Name AD1 Address & Name
ADCR A/D Control Register. The ADCR register must be written to select the operating mode before A/D conversion can occur. R/W 0x0000 0001 0xE003 4000 AD0CR 0xE006 0000 AD1CR
ADGDR A/D Global Data Register. This register contains the ADC’s DONE bit and the result of the most recent A/D conversion. R/W NA 0xE003 4004 AD0GDR 0xE006 0004 AD1GDR
ADSTAT A/D Status Register. This register contains DONE and OVERRUN flags for all of the A/D channels, as well as the A/D interrupt flag. RO 0x0000 0000 0xE003 4030 AD0STAT 0xE006 0030 AD1STAT
"""

print("--- CLEANED CONTEXT ---")
cleaned = clean_context(context, peripheral="ADC")
print(cleaned)
print("\n--- REGISTER SUMMARY ---")
summary = extract_register_summary(cleaned)
try:
    print(summary.encode('utf-8').decode('ascii', 'ignore'))
except Exception:
    print("\n[Summary received but contained non-ascii characters]")
