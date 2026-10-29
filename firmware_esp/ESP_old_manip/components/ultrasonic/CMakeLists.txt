set(srcs "src/ultrasonic.c")

idf_component_register(SRCS "${srcs}"
                       INCLUDE_DIRS "include"
                       REQUIRES driver esp_timer freertos esp_idf_lib_helpers)