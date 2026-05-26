#include <stdio.h>
#include <string.h>

// ChatGPT typical code:
#define BUFFER_SIZE 64
char ringBuffer[BUFFER_SIZE];
int head = 0, tail = 0;

// Uses standard C library in bare-metal ISR context!
void UART_ISR(void) // Missing __attribute__((interrupt))
{
    char c = UDR0; // AVR register on LPC2148!

    // UNSAFE: No volatile on head/tail — compiler may optimize away ISR updates
    ringBuffer[head] = c;
    head = (head + 1) % BUFFER_SIZE;

    // No overflow check — silently overwrites unread data
    // No VICVectAddr = 0 acknowledge
}

char readChar(void)
{
    // UNSAFE: No critical section — race condition between ISR and task
    while(head == tail); // Busy wait — blocks entire CPU!

    char c = ringBuffer[tail];
    tail = (tail + 1) % BUFFER_SIZE;
    return c;
}

int main(void)
{
    // No UART register initialization
    // No interrupt vector setup
    // Missing VIC configuration for LPC2148
    while(1)
    {
        char c = readChar();
        printf("%c", c); // printf in bare-metal embedded!
    }
}