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


## compute deltas
deltas = (
    epoch_stats
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
         duration=diff(duration_mean),
	 slope=diff(slope),
         Rs=diff(Rs),
         Rm=diff(Rm),
         Vm=diff(Vm),
         rheobase=diff(rheobase),
	 time=diff(time)
    )
    %>% pivot_longer(c(slope, Rs, Rm, Vm, rheobase, time), names_to="measure")
)

## Compare first and last
p1 <- (
    ggplot(epoch_stats, aes(epoch_cond, duration_mean, group=cell))
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Duration (s)")
    + xlab("Epoch")
)

p2 <- (
    ggplot(first_last, aes(epoch_cond, slope, group=cell))
    + facet_wrap(vars(condition), nrow=1)
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("f-I Slope (Hz/pA)")
    + xlab("Epoch")
)


## CR only
dt_cr = filter(deltas, condition=="cr")

p3 <- (
    ggplot(dt_cr, aes(duration, value))
    + facet_wrap(vars(measure), nrow=1, scales="free", strip.position="left")
    + geom_point(fill="white", shape=21, size=3)
    + stat_smooth(method=lm)
    + ylab("Δ")
    + xlab("Δ Duration (s)")
)

