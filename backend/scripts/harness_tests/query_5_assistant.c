#include "FreeRTOS.h"
#include "task.h"

// ChatGPT typical code:
void vADCTask(void *pvParameters)
{
    // AVR register configuration (ADCSRA, ADMUX) on an LPC2148 target!
    ADCSRA = (1<<ADEN) | (1<<ADPS2); // Architecture mismatch
    ADMUX = (1<<REFS0) | 1;
    
    for(;;)
    {
        ADCSRA |= (1<<ADSC); // Start conversion
        while(ADCSRA & (1<<ADSC)); // Polling
        
        int adc_val = ADC;
        // Simple moving average with uninitialized memory
        vTaskDelay(100);
    }
}

int main(void)
{
    xTaskCreate(vADCTask, "ADC", 128, NULL, 1, NULL);
    vTaskStartScheduler();
}