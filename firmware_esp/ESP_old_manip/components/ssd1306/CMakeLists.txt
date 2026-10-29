set(srcs "src/ssd1306.c" "src/ssd1306_i2c.c" "src/ssd1306_spi.c")

idf_component_register(SRCS "${srcs}"
                       INCLUDE_DIRS "include"
                       REQUIRES driver)