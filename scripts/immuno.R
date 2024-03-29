library(readr)
library(dplyr)
library(tidyr)
library(lmerTest)
library(emmeans)
library(ggplot2)

my.theme <- theme_classic() + theme(legend.position="none",
                                    axis.line=element_line(size=0.25),
				    axis.ticks=element_line(size=0.25),
				    axis.title=element_text(size=6),
                                    axis.text=element_text(size=5),
				    strip.placement="outside",
				    strip.text=element_text(size=6),
				    strip.background=element_blank())
update_geom_defaults("point", list(fill="white", shape=21, size=1.1))
update_geom_defaults("line", list(linewidth=0.25))

## Only including batches 1 and 3 (4 and 5 had issues with sample prep)
counts <- (
       read_csv("inputs/immuno_counts.csv",
                col_types=cols(
                               file_orig = col_skip(),
			       bird = col_character(),
  			       batch = col_factor(),
  			       section = col_factor(),
  			       stack = col_factor(),
  			       dapi = col_double(),
  			       neurotrace = col_double(),
  			       kv11 = col_double(),
  			       volume = col_double(),
  			       counter = col_character(),
  			       include = col_integer(),
			       comments = col_skip()
	))
	%>% filter(include==1, batch %in% c(1,3))
	%>% mutate(total.density=dapi/volume, kv11.density=kv11/volume, prop=kv11/dapi)
)

## inspection plot to look for outliers w/in bird
counts %>% group_by(bird, section, stack) %>%
    summarize(prop=mean(prop), density=mean(density)) %>%
    ggplot(aes(bird, density)) + geom_boxplot()

## ggplot(counts, aes(bird, total.density)) + facet_grid(~ batch, scale="free", space="free") + geom_boxplot()	

## Only analyzing CR and PR for this paper
birds <- (
  read_csv("inputs/immuno_birds.csv",
           col_types=cols(
  	       bird = col_character(),
  	       sire = col_character(),
  	       condition = col_character(),
  	       sex = col_character(),
  	       age = col_double()
	       )
	  )
   %>% mutate(condition=factor(condition, levels=c("CR", "PR", "AM", "BR")))
   %>% filter(condition %in% c("CR", "PR"))
)

## unblinded data
df = inner_join(counts, birds, by=c("bird"))

## sire cannot be included as a random effect or the fit is singular
(fm_c <- glmer(cbind(kv11, dapi - kv11) ~ condition + (1|bird/section/stack) + (1|batch), family="binomial", data=df))
(em_c <- emmeans(fm_c, ~ condition))
(ci_c <- bind_cols(
    confint(em_c, level=0.50, type="response"),
    confint(em_c, level=0.90, type="response") %>% select(asymp.LCL.90=asymp.LCL, asymp.UCL.90=asymp.UCL)))
    
plt <- (
    ci_c
    %>% ggplot(aes(condition, prob))
    + geom_linerange(aes(ymin=asymp.LCL, ymax=asymp.UCL), linewidth=1.5)
    + geom_linerange(aes(ymin=asymp.LCL.90, ymax=asymp.UCL.90))
    + geom_point(size=1.5)
    + scale_y_continuous("p(Kv1.1)", limits=c(0,1))
)
pdf("figures/cr_pr_kv11.pdf", width=1.25, height=1.4)
print(plt + my.theme)
dev.off()

## EM
em_counts <- inner_join(read_csv("inputs/em_counts.csv"), birds, by="bird")

## too few replicates to do mixed effects modeling, so we're just going to use
## naive nonparametric stats. The standard procedure for Erisir lab is to do a
## kruskal-wallace with bird as the factor and then pool within condition if
## there is no significant post-hoc difference among the birds within condition.
## I'm not going to try to replicate that here.

p2.1 <- (
    select(em_counts, bird, condition, y=pm.density)
    %>% ggplot(aes(condition, y=y))
    + geom_boxplot(width=0.15, position=position_nudge(0.2))
    + geom_jitter(aes(color=bird), width=0.05)
    + scale_y_continuous("Linear density (clusters/μm)")
)
p2.2 <- (
     p2.1
     %+% select(em_counts, bird, condition, y=nm.density)
)

p2.3 <- (
     p2.1
     %+% select(em_counts, bird, condition, y=er.count)
     + scale_y_continuous("Clusters")
)
p2.4 <- (
     p2.1
     %+% select(em_counts, bird, condition, y=total.count)
     + scale_y_continuous("Clusters")
)
pdf("figures/em_density_counts.pdf", width=2.9, height=3.0)
egg::ggarrange(
     p2.1 + my.theme, p2.2 + my.theme,
     p2.3 + my.theme, p2.4 + my.theme,
     nrow=2)
dev.off()
