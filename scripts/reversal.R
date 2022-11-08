### quantify reversal of plasticity with potassium channel blockers
library(readr)
library(stringr)
library(tidyr)
library(dplyr)
library(ggplot2)

my.theme <- egg::theme_article() + theme(legend.position="none",
                              	         axis.title=element_text(size=8),
                                         axis.text=element_text(size=6))

## epoch types are tagged in the control file
## select first, last (pre), and post epochs for each cell
## There are no narrow-spiking cells, but we only look at initially tonic neurons
reversal_epochs = read_csv("inputs/reversal_epochs.csv")
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(reversal_epochs, by=c("cell", "epoch"))
    %>% filter(epoch_cond %in% c("first", "pre", "post"))
    %>% mutate(epoch_cond=factor(epoch_cond, levels=c("first", "pre", "post")))
    %>% group_by(cell)
    %>% filter(first(duration_mean) > 1.0)
)

## Compare first and last
p1 <- (
    ggplot(epoch_stats, aes(epoch_cond, duration_mean, group=cell))
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Duration (s)")
    + xlab("Epoch")
)

