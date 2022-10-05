
library(readr)
library(dplyr)

coloc_epochs = read_csv("inputs/colocalization_epochs.csv")
biocytin_cells = read_csv("inputs/biocytin_cells.csv") %>% select(cell, kv11) %>% filter(!is.na(cell), !is.na(kv11))
epoch_stats = read_csv("build/epoch_stats.csv") %>% semi_join(coloc_epochs, by=c("cell", "epoch"))

## select first epoch
## cell_stats = group_by(epoch_stats, cell) %>% arrange(epoch) %>% filter(row_number()==1) %>% inner_join(biocytin_cells, by="cell")

## average epochs
cell_stats = (
     group_by(epoch_stats, cell) %>%
     summarize(duration_mean=mean(duration_mean, na.rm=T), slope_mean=mean(slope, na.rm=T)) %>%
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
