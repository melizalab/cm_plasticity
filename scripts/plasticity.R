library(stringr)
library(readr)
library(dplyr)
library(ggplot2)

plasticity_epochs = (
    read_csv("inputs/plasticity_epochs.csv")
    %>% mutate(cell=str_sub(cell, end=8))
)
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(plasticity_epochs, by=c("cell", "epoch"))
)

## select first and last epochs for each cell and tag them
## drop narrow-spiking cells (note: assumes that spike width remains ~constant from first to last)
first_last = (
    epoch_stats
    %>% arrange(cell, epoch)
    %>% group_by(cell)
    %>% mutate(epoch_cond=ifelse(row_number()==1, "first", ifelse(row_number()==n(), "last", "mid")))
    %>% filter(epoch_cond %in% c("first", "last"))
    %>% filter(spike_width > 0.9)
)

## CR only
df_cr = filter(first_last, condition=="cr")
ggplot(df, aes(epoch_cond, duration_mean, group=cell)) + geom_point() + geom_line()