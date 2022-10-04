
library(readr)
library(dplyr)

biocytin_cells = read_csv("inputs/biocytin_cells.csv") %>% select(cell, kv11) %>% filter(!is.na(cell), !is.na(kv11))

epoch_stats = read_csv("build/epoch_stats.csv")

## select first epoch
cell_stats = group_by(epoch_stats, cell) %>% arrange(epoch) %>% filter(row_number()==1) %>% inner_join(biocytin_cells, by="cell")

## average epochs
cell_stats = group_by(epoch_stats, cell) %>% summarize(duration_mean=mean(duration_mean, na.rm=T)) %>% inner_join(biocytin_cells, by="cell")

ggplot(cell_stats, aes(kv11, duration_mean)) + geom_jitter(width=0.1)

