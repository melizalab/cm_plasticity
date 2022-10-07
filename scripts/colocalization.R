library(readr)
library(dplyr)
library(ggplot2)

coloc_epochs = read_csv("inputs/colocalization_epochs.csv")
biocytin_cells = read_csv("inputs/biocytin_cells.csv") %>% select(cell, kv11) %>% filter(!is.na(cell), !is.na(kv11))
epoch_stats = read_csv("build/epoch_stats.csv") %>% semi_join(coloc_epochs, by=c("cell", "epoch"))

## average epochs
cell_stats = (
     group_by(epoch_stats, cell) %>%
     ## this would select first epoch
     ## arrange(epoch) %>% filter(row_number()==1) %>%
     summarize(duration_mean=mean(duration_mean, na.rm=T),
               slope_mean=mean(slope, na.rm=T),
	       spike_width=median(spike_width, na.rm=T),
	       temperature=median(temperature, na.rm=T)) %>%
     ## filter out narrow-spiking cells       
     filter(spike_width > 0.9) %>%
     inner_join(biocytin_cells, by="cell") 
)

## TODO make this look pretty
pdf("figures/kv11_duration.pdf)
ggplot(cell_stats, aes(kv11, duration_mean)) +
      geom_jitter(width=0.1) +
      ylab("Duration (s)")
dev.off()

## simple stats:
wilcox.test(duration_mean ~ kv11, cell_stats)
