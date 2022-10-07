library(readr)
library(stringr)
library(tidyr)
library(dplyr)
library(ggplot2)

my.theme <- egg::theme_article() + theme(legend.position="none",
                              	         axis.title=element_text(size=8),
                                         axis.text=element_text(size=6))

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
    %>% arrange(cell, epoch)
)

## compute deltas
deltas = (
    first_last
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
         duration=diff(duration_mean),
	 slope=diff(slope),
         Rs=diff(Rs),
         Rm=diff(Rm),
         Vm=diff(Vm),
         rheobase=diff(rheobase)
    )
)

## CR only
df_cr = filter(first_last, condition=="cr")
dt_cr = filter(deltas, condition=="cr")

p1 <- ggplot(df_cr, aes(epoch_cond, duration_mean, group=cell)) + geom_point() + geom_line()
p2 <- ggplot(dt_cr, aes(duration, slope)) + geom_point(fill="white", shape=21, size=3) + ylab("Δ Slope (Hz/pA)") + xlab("Δ Duration (s)")
ggplot(df, aes(duration, value)) + facet_wrap(vars(measure), nrow=1, scales="free", strip.position="left") + geom_point(fill="white", shape=21, size=3) + stat_smooth(method=lm)
