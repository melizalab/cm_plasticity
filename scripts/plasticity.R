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
    %>% mutate(cell=str_sub(cell, end=8), condition=factor(condition, levels=c("cr", "noinj", "pr", "bapta")))
)
cell_info = (
    read_csv("build/cell_info.csv")
    %>% mutate(bird=str_sub(bird, end=8), sire=str_sub(sire, end=8), dam=str_sub(dam, end=8))
)
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(plasticity_epochs, by=c("cell", "epoch"))
    %>% inner_join(cell_info, by="cell")
)

## Check for exclusions:
select(epoch_stats, cell, epoch, Vm, delta_Rs, delta_Rm) %>% group_by(cell) %>% filter(any(abs(delta_Rs) > 0.3))
select(epoch_stats, cell, epoch, Rs, Rm, Vm, delta_Vm) %>% group_by(cell) %>% filter(any(delta_Vm > 10))
select(epoch_stats, cell, epoch, Vm, n_spont) %>% group_by(cell) %>% filter(any(n_spont > 5))

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

## CR only
## 1. Duration and slope spaghetti plots
## 2. change in duration vs time
## 3. other correlations
fl_cr = filter(first_last, condition=="cr")

## compute deltas
dt_cr = (
    fl_cr
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
	 duration=diff(duration_mean),
	 time=diff(time)
    )
)

p1 <- (
    dt_cr
    %>% ggplot(aes(time, duration))
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Δ Duration (s)")
    + xlab("Time (s)")
)

## All conditions:
## drop neurons where time is less than 400 s (need enough time to see plasticity)
too_short = (
    first_last
    %>% group_by(cell)
    %>% filter(last(time) < 400)
    %>% select(cell, epoch, condition, time)
)
fl_all = anti_join(first_last, too_short, by="cell")
dt_all = (
    fl_all
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
         duration=diff(duration_mean),
	 slope=diff(slope),
         Rs=diff(Rs),
         Rm=diff(Rm),
         Vm=diff(Vm),
         rheobase=diff(rheobase),
	 )
    %>% inner_join(cell_info, by="cell")
)


## Compare first and last
p2 <- (
    ggplot(fl_all, aes(epoch_cond, duration_mean, group=cell))
    + facet_wrap(vars(condition), nrow=1)
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Duration (s)")
    + xlab("Epoch")
)

## correlate change in duration with other variables
p3 <- (
   filter(dt_all, condition=="cr")
   %>% pivot_longer(c(slope, Rs, Rm, Vm, rheobase), names_to="measure")
   %>% ggplot(aes(duration, value))
    + facet_wrap(vars(measure), nrow=1, scales="free", strip.position="left")
    + geom_point(fill="white", shape=21, size=3)
    + stat_smooth(method=lm)
    + ylab("Δ")
    + xlab("Δ Duration (s)")
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

