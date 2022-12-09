library(readr)
library(dplyr)
library(ggplot2)
library(stringr)

my.theme <- theme_classic() + theme(legend.position="none",
                                    axis.line=element_line(linewidth=0.25),
				    axis.title=element_text(size=6),
                                    axis.text=element_text(size=5),
				    strip.placement="outside",
				    strip.text=element_text(size=6),
				    strip.background=element_blank())
update_geom_defaults("point", list(fill="white", shape=21, size=1.1))
update_geom_defaults("line", list(linewidth=0.25))

coloc_epochs = read_csv("inputs/colocalization_epochs.csv")
biocytin_cells_yao = (
     read_csv("inputs/biocytin_cells.csv")
     ## %>% filter(!is.na(cell), !is.na(kv11))
)
biocytin_cells = (
     read_csv("inputs/biocytin_cells_dan.csv")
     %>% filter(!is.na(cell), !is.na(kv11))
)
epoch_stats = read_csv("build/epoch_stats.csv") %>% semi_join(coloc_epochs, by=c("cell", "epoch"))

## average epochs
## filter out narrow-spiking cells       
cell_stats = (
     group_by(epoch_stats, cell) 
     %>% summarize(duration_mean=mean(duration_mean, na.rm=T),
                  slope_mean=mean(slope, na.rm=T),
	          spike_width=median(spike_width, na.rm=T),
	          temperature=median(temperature, na.rm=T))
      %>% filter(spike_width > 0.9)
      %>% inner_join(biocytin_cells, by="cell")
)

## manual classification:
p1 <- (
   cell_stats
   %>% ggplot(aes(kv11, duration_mean))
   + geom_jitter(width=0.1)
   + ylab("Duration (s)")
   + xlab("Kv1.1")
)

## simple stats:
wilcox.test(duration_mean ~ kv11, cell_stats)

## TODO make this look pretty

## automated pipeline
section_thickness <- 0.44
## combine counts across sections in kv11 ihc data
kv11_stats = (
     read_csv(
         "inputs/kv11_puncta.csv",
         col_names=c("image", "opt_section", "puncta", "area", "density", "coloc"),
         skip=1
     )
     ## strip off last part of name (denotes objective power)
     %>% mutate(image=str_replace(image, "_[0-9]+$", ""))
     %>% group_by(image)
     %>% summarize(puncta=sum(puncta), volume=sum(area) * section_thickness)
     %>% mutate(density=puncta/volume * 1000)
)

p2 <- (
   cell_stats
   %>% left_join(kv11_stats, by="image")
   %>% ggplot(aes(density, duration_mean))
   + geom_point()
   + ylab("Duration (s)")
   + xlab("Kv1.1 density (puncta / 1000 μm³)")
)

pdf("figures/duration_kv11.pdf", width=1.5, height=2.2)
egg::ggarrange(p1 + my.theme, p2 + my.theme)
dev.off()

## Statistics:
library(lme4)
library(emmeans)

sweep_stats = (
    read_csv("build/sweep_stats.csv")
    %>% filter(!is.na(firing_duration))
    %>% semi_join(coloc_epochs, by=c("cell", "epoch"))
    %>% inner_join(kv11_stats, by="cell")
)

